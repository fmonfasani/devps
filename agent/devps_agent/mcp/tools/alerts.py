"""Alert management tools — thin adapters to alerting.py."""

from datetime import datetime, timedelta, UTC
from typing import Any

from ... import registry
from ..context import MCPContext
from .  import register_tool
from ...db import connect


async def _configure_alerts(
    context: MCPContext,
    project_name: str,
    email: str = None,
    slack: str = None,
    enabled: bool = True,
    **kwargs
) -> dict[str, Any]:
    """Configure alerts for a project.

    Updates alert_email, alert_slack, alert_enabled in projects table.
    """
    context.require_permission("edit_project", project_name)

    project = registry.get_project(project_name)
    if not project:
        raise ValueError(f"Project {project_name!r} not found")

    # Update settings
    with connect() as conn:
        conn.execute(
            "UPDATE projects SET alert_email = ?, alert_slack = ?, alert_enabled = ? WHERE name = ?",
            (email or None, slack or None, enabled, project_name),
        )

    return {
        "success": True,
        "project_name": project_name,
    }


async def _mute_alerts(
    context: MCPContext,
    project_name: str,
    hours: int = 1,
    **kwargs
) -> dict[str, Any]:
    """Mute alerts for a project temporarily.

    Updates alert_muted_until timestamp.
    """
    context.require_permission("edit_project", project_name)

    project = registry.get_project(project_name)
    if not project:
        raise ValueError(f"Project {project_name!r} not found")

    # Validate hours
    hours = max(1, min(hours, 24))

    # Calculate muted_until timestamp
    muted_until = datetime.now(UTC) + timedelta(hours=hours)

    # Update database
    with connect() as conn:
        conn.execute(
            "UPDATE projects SET alert_muted_until = ? WHERE name = ?",
            (muted_until.isoformat(), project_name),
        )

    return {
        "success": True,
        "project_name": project_name,
        "muted_until": muted_until.isoformat(),
    }


async def _unmute_alerts(context: MCPContext, project_name: str, **kwargs) -> dict[str, Any]:
    """Unmute alerts for a project.

    Clears alert_muted_until timestamp.
    """
    context.require_permission("edit_project", project_name)

    project = registry.get_project(project_name)
    if not project:
        raise ValueError(f"Project {project_name!r} not found")

    # Clear muted_until
    with connect() as conn:
        conn.execute(
            "UPDATE projects SET alert_muted_until = NULL WHERE name = ?",
            (project_name,),
        )

    return {
        "success": True,
        "project_name": project_name,
    }


def register_alerts_tools() -> None:
    """Register alert management tools."""
    register_tool("devps.alerts.configure", _configure_alerts)
    register_tool("devps.alerts.mute", _mute_alerts)
    register_tool("devps.alerts.unmute", _unmute_alerts)
