"""Health status endpoints."""

from fastapi import APIRouter, HTTPException

from .. import registry

router = APIRouter(prefix="/projects", tags=["health"])


@router.get("/{name}/health")
def get_health(name: str) -> dict:
    """Get health status and metrics for a project.

    Returns:
    {
        "project_name": str,
        "health_status": "running" | "dead" | "unhealthy" | "unknown",
        "restart_count": int,
        "last_restart_at": ISO8601 timestamp or null,
        "last_health_check_at": ISO8601 timestamp or null,
        "status": "deployed" | "build_failed" | etc,
        "managed_by": "devps" | "adopted"
    }
    """
    project = registry.get_project(name)
    if project is None:
        raise HTTPException(404, "not found")

    return {
        "project_name": project["name"],
        "health_status": project.get("health_status", "unknown"),
        "restart_count": project.get("restart_count", 0),
        "last_restart_at": project.get("last_restart_at"),
        "last_health_check_at": project.get("last_health_check_at"),
        "status": project["status"],
        "managed_by": project["managed_by"],
    }


@router.get("")
def list_health() -> list[dict]:
    """Get health status for all projects.

    Returns list of health status objects (same as /projects/{name}/health).
    """
    projects = registry.list_projects()
    return [
        {
            "project_name": p["name"],
            "health_status": p.get("health_status", "unknown"),
            "restart_count": p.get("restart_count", 0),
            "last_restart_at": p.get("last_restart_at"),
            "last_health_check_at": p.get("last_health_check_at"),
            "status": p["status"],
            "managed_by": p["managed_by"],
        }
        for p in projects
    ]
