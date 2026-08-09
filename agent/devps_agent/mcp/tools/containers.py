"""Container management tools — thin adapters to docker_ops.py."""

from typing import Any

from ... import docker_ops, registry, rbac
from ..context import MCPContext
from . import register_tool


async def _container_status(context: MCPContext, project_name: str, **kwargs) -> dict[str, Any]:
    """Get container status.

    Delegated to docker_ops.container_health().
    """
    context.require_permission("view_health")

    project = registry.get_project(project_name)
    if not project:
        raise ValueError(f"Project {project_name!r} not found")

    status = docker_ops.container_health(project_name)

    return {
        "project_name": project_name,
        "status": status,
    }


async def _container_restart(context: MCPContext, project_name: str, **kwargs) -> dict[str, Any]:
    """Restart a container.

    Delegated to docker_ops.compose_restart().
    """
    context.require_permission("edit_project", project_name)

    project = registry.get_project(project_name)
    if not project:
        raise ValueError(f"Project {project_name!r} not found")

    if project["managed_by"] != "devps":
        raise ValueError("Project not managed by devps")

    # Get project directory
    from ... import config
    from pathlib import Path

    project_dir = Path(config.PROJECTS_DIR) / project_name

    # Restart container
    docker_ops.compose_restart(project_dir, "docker-compose.yml")

    # Log event
    registry.log_event(
        project_name,
        "manual_restart",
        f"Restarted via MCP by {context.username}",
        success=True,
    )

    return {
        "success": True,
        "message": "Container restarted",
    }


async def _container_logs(
    context: MCPContext, project_name: str, tail: int = 200, **kwargs
) -> dict[str, Any]:
    """Get container logs.

    Delegated to docker_ops.container_logs().
    """
    context.require_permission("view_project", project_name)

    project = registry.get_project(project_name)
    if not project:
        raise ValueError(f"Project {project_name!r} not found")

    # Validate tail
    tail = max(10, min(tail, 1000))

    logs = docker_ops.container_logs(project_name, tail)

    return {
        "project_name": project_name,
        "logs": logs,
    }


def register_containers_tools() -> None:
    """Register container management tools."""
    register_tool("devps.containers.status", _container_status)
    register_tool("devps.containers.restart", _container_restart)
    register_tool("devps.containers.logs", _container_logs)
