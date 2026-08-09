"""Migration tracking tools — thin adapters to registry.py."""

from typing import Any

from ... import registry
from ..context import MCPContext
from . import register_tool


async def _list_migrations(context: MCPContext, **kwargs) -> dict[str, Any]:
    """List all project migrations.

    Delegated to registry.list_migrations().
    """
    context.require_permission("view_project")

    migrations = registry.list_migrations()

    return {
        "migrations": migrations,
    }


async def _transition_migration(
    context: MCPContext,
    project_name: str,
    step: str,
    source_description: str = None,
    **kwargs
) -> dict[str, Any]:
    """Transition a migration to next step.

    Steps: adopted → paralleled → cutover → decommissioned
    Admin only.
    """
    context.require_permission("edit_project")

    project = registry.get_project(project_name)
    if not project:
        raise ValueError(f"Project {project_name!r} not found")

    # Validate step
    valid_steps = ["paralleled", "cutover", "decommissioned"]
    if step not in valid_steps:
        raise ValueError(f"Invalid step: {step!r}. Must be one of {valid_steps}")

    # Update migration
    registry.touch_migration(project_name, step, source_description)

    return {
        "success": True,
        "project_name": project_name,
        "step": step,
    }


def register_migrations_tools() -> None:
    """Register migration tracking tools."""
    register_tool("devps.migrations.list", _list_migrations)
    register_tool("devps.migrations.transition", _transition_migration)
