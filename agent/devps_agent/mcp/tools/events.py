"""Event log tools — thin adapters to registry.py."""

from typing import Any

from ... import registry
from ..context import MCPContext
from . import register_tool


async def _get_events(
    context: MCPContext,
    project_name: str,
    limit: int = 100,
    **kwargs
) -> dict[str, Any]:
    """Get events for a specific project.

    Delegated to registry.get_events().
    """
    context.require_permission("view_events")

    project = registry.get_project(project_name)
    if not project:
        raise ValueError(f"Project {project_name!r} not found")

    # Validate limit
    limit = max(10, min(limit, 500))

    events = registry.get_events(project_name, limit)

    return {
        "project_name": project_name,
        "events": events,
    }


async def _list_events(context: MCPContext, limit: int = 200, **kwargs) -> dict[str, Any]:
    """Get global event log (all projects).

    Delegated to registry.list_events().
    """
    context.require_permission("view_events")

    # Validate limit
    limit = max(10, min(limit, 500))

    events = registry.list_events(limit)

    return {
        "events": events,
    }


def register_events_tools() -> None:
    """Register event log tools."""
    register_tool("devps.events.get", _get_events)
    register_tool("devps.events.list", _list_events)
