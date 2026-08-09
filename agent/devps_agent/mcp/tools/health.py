"""Health monitoring tools — thin adapters to health_checks.py."""

from typing import Any

from ... import docker_ops, registry
from ..context import MCPContext
from . import register_tool


async def _health_status(context: MCPContext, **kwargs) -> dict[str, Any]:
    """Get health status of all projects.

    Delegated to docker_ops.container_health() for each project.
    """
    context.require_permission("view_health")

    projects = registry.list_projects()
    health_list = []

    for project in projects:
        status = docker_ops.container_health(project["name"])
        health_list.append({
            "name": project["name"],
            "status": status,
            "restart_count": project.get("restart_count", 0),
            "last_check": project.get("updated_at"),
        })

    return {
        "projects": health_list,
    }


async def _health_check(context: MCPContext, project_name: str, **kwargs) -> dict[str, Any]:
    """Perform immediate health check on a project.

    Returns current container status without triggering auto-restart.
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


def register_health_tools() -> None:
    """Register health monitoring tools."""
    register_tool("devps.health.status", _health_status)
    register_tool("devps.health.check", _health_check)
