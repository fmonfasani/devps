"""Project management tools — thin adapters to registry.py."""

import json
from typing import Any

from ... import rbac, registry
from ..context import MCPContext
from ..schemas import ProjectsListRequest, ProjectGetRequest
from . import register_tool


async def _list_projects(context: MCPContext, **kwargs) -> dict[str, Any]:
    """List projects accessible to the authenticated user.

    Delegated from devps.projects.list to registry.list_projects().
    Filtered by user permissions (RBAC).
    """
    # Check permission
    context.require_permission("list_projects")

    # Get all projects
    all_projects = registry.list_projects()

    # Filter by user role (same logic as dashboard)
    if context.user["role"] == "admin" or context.user["role"] == "viewer":
        # Admins and viewers see all projects
        projects = all_projects
    elif context.user["role"] == "deployer":
        # Deployers see only their own projects
        projects = [p for p in all_projects if p.get("owner") == context.username]
    else:
        projects = []

    # Apply additional filters if provided
    filter_owner = kwargs.get("filter_owner")
    if filter_owner:
        projects = [p for p in projects if p.get("owner") == filter_owner]

    filter_status = kwargs.get("filter_status")
    if filter_status:
        projects = [p for p in projects if p.get("status") == filter_status]

    return {
        "projects": projects
    }


async def _get_project(context: MCPContext, name: str, **kwargs) -> dict[str, Any]:
    """Get detailed information about a specific project.

    Delegated from devps.projects.get to registry.get_project().
    Checks user permissions (RBAC).
    """
    # Get project
    project = registry.get_project(name)
    if not project:
        raise ValueError(f"Project {name!r} not found")

    # Check permission (viewer role required)
    context.require_permission("view_project", name)

    return {
        "project": project
    }


async def _delete_project(context: MCPContext, name: str, **kwargs) -> dict[str, Any]:
    """Delete a project.

    Delegated from devps.projects.delete to registry.delete_project().
    Admin only.
    """
    # Check permission (admin only)
    context.require_permission("delete_project")

    # Check project exists
    project = registry.get_project(name)
    if not project:
        raise ValueError(f"Project {name!r} not found")

    # Delete project
    registry.delete_project(name)

    return {
        "success": True,
        "message": f"Project {name!r} deleted",
    }


def register_projects_tools() -> None:
    """Register project management tools."""
    register_tool(
        "devps.projects.list",
        _list_projects,
    )
    register_tool(
        "devps.projects.get",
        _get_project,
    )
    register_tool(
        "devps.projects.delete",
        _delete_project,
    )
