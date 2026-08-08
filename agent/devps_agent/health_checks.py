"""Health monitoring and auto-recovery for deployed projects."""

import asyncio
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from . import config, docker_ops, registry


class HealthCheckError(Exception):
    """Health check operation failed."""

    pass


class RestartRateLimiter:
    """Simple in-memory rate limiter for auto-restarts.

    Limits restarts to MAX_RESTARTS_PER_HOUR per project to prevent
    restart loops (e.g., if the container immediately crashes).
    """

    MAX_RESTARTS_PER_HOUR = 5

    def __init__(self) -> None:
        self.restart_times: dict[str, list[datetime]] = defaultdict(list)

    def can_restart(self, project_name: str) -> bool:
        """Check if project can be restarted (rate limit not exceeded)."""
        now = datetime.now(UTC)
        one_hour_ago = now - timedelta(hours=1)

        # Clean old timestamps
        self.restart_times[project_name] = [
            ts for ts in self.restart_times[project_name] if ts > one_hour_ago
        ]

        return len(self.restart_times[project_name]) < self.MAX_RESTARTS_PER_HOUR

    def record_restart(self, project_name: str) -> None:
        """Record a restart attempt."""
        self.restart_times[project_name].append(datetime.now(UTC))

    def get_restart_count(self, project_name: str) -> int:
        """Get number of restarts in the last hour."""
        now = datetime.now(UTC)
        one_hour_ago = now - timedelta(hours=1)
        self.restart_times[project_name] = [
            ts for ts in self.restart_times[project_name] if ts > one_hour_ago
        ]
        return len(self.restart_times[project_name])


_restart_limiter = RestartRateLimiter()


def check_container_health(project_name: str) -> str:
    """Check if a project's container is running and healthy.

    Returns:
        "running" — container is up and healthy
        "dead" — container exited or doesn't exist
        "unhealthy" — health check failed (if configured)

    Raises:
        HealthCheckError: If check operation fails
    """
    try:
        info = docker_ops.inspect_container(project_name)
        if info is None:
            return "dead"

        state = info.get("State", {})
        if not state.get("Running"):
            return "dead"

        # Check health status if health check is configured
        health = state.get("Health", {}).get("Status")
        if health and health != "healthy":
            return "unhealthy"

        return "running"
    except docker_ops.CommandError as e:
        raise HealthCheckError(f"Failed to check container: {e}") from e


def update_health_status(project_name: str, status: str) -> None:
    """Update health status in registry.

    Args:
        project_name: Project name
        status: "running", "dead", or "unhealthy"
    """
    from .db import connect

    with connect() as conn:
        conn.execute(
            """UPDATE projects SET health_status = ?, last_health_check_at = ?
               WHERE name = ?""",
            (status, datetime.now(UTC).isoformat(), project_name),
        )


def restart_container(project_name: str) -> bool:
    """Attempt to restart a project's container.

    Rate-limited to 5 restarts per hour to prevent restart loops.

    Returns:
        True if restart succeeded, False otherwise
    """
    project = registry.get_project(project_name)
    if not project:
        return False

    if project["managed_by"] != "devps":
        return False

    # Check rate limit
    if not _restart_limiter.can_restart(project_name):
        count = _restart_limiter.get_restart_count(project_name)
        registry.log_event(
            project_name,
            "auto_restart",
            f"rate limit exceeded ({count}/hour), skipping restart",
            success=False,
        )
        return False

    try:
        docker_ops.compose_restart(
            config.PROJECTS_DIR / project_name, project.get("compose_file", "docker-compose.yml")
        )
        _restart_limiter.record_restart(project_name)
        _increment_restart_count(project_name)
        registry.log_event(
            project_name,
            "auto_restart",
            "health check detected dead container, restarted",
            success=True,
        )
        return True
    except docker_ops.CommandError as e:
        registry.log_event(
            project_name,
            "auto_restart",
            f"restart failed: {e}",
            success=False,
        )
        return False


def _increment_restart_count(project_name: str) -> None:
    """Increment restart counter and update timestamp."""
    from .db import connect

    now = datetime.now(UTC).isoformat()
    with connect() as conn:
        conn.execute(
            """UPDATE projects
               SET restart_count = restart_count + 1,
                   last_restart_at = ?
               WHERE name = ?""",
            (now, project_name),
        )


async def health_check_loop() -> None:
    """Background health monitoring loop.

    Runs every CHECK_INTERVAL seconds:
    1. Check health of each deployed project
    2. If dead → auto-restart
    3. Track restart count and timestamps
    4. Log events

    Runs until task is cancelled.
    """
    CHECK_INTERVAL = 30  # seconds

    while True:
        try:
            await asyncio.sleep(CHECK_INTERVAL)

            projects = registry.list_projects()
            for project in projects:
                if project["managed_by"] != "devps":
                    continue

                try:
                    health = check_container_health(project["name"])
                    update_health_status(project["name"], health)

                    if health == "dead":
                        restart_container(project["name"])
                    elif health == "unhealthy":
                        # Log but don't auto-restart (let user investigate)
                        registry.log_event(
                            project["name"],
                            "health_check",
                            "container unhealthy, manual intervention may be needed",
                            success=True,
                        )

                except HealthCheckError as e:
                    registry.log_event(
                        project["name"],
                        "health_check",
                        f"health check failed: {e}",
                        success=False,
                    )

        except asyncio.CancelledError:
            break
        except Exception as e:
            # Log unexpected errors but don't crash the loop
            print(f"Health check loop error: {e}")
            await asyncio.sleep(5)
