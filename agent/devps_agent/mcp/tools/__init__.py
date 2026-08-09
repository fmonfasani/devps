"""MCP tool implementations — thin adapters to DEVPS capabilities.

Each tool delegates to existing DEVPS modules (registry, docker_ops, etc).
No business logic duplication.
"""

from typing import Dict, Callable, Any

# Registry of all available tools
TOOLS: Dict[str, Callable] = {}


def register_tool(name: str, handler: Callable) -> None:
    """Register a tool handler.

    Args:
        name: Tool name (e.g., "devps.projects.list")
        handler: Async function that executes the tool
    """
    TOOLS[name] = handler


def get_tool(name: str) -> Callable | None:
    """Get tool handler by name."""
    return TOOLS.get(name)


def list_tools() -> list[str]:
    """Get list of all registered tool names."""
    return sorted(TOOLS.keys())


# Register all tools on module load (import after function definitions to avoid circular imports)
from .projects import register_projects_tools
from .containers import register_containers_tools
from .health import register_health_tools
from .alerts import register_alerts_tools
from .events import register_events_tools
from .migrations import register_migrations_tools
from .users import register_users_tools

register_projects_tools()
register_containers_tools()
register_health_tools()
register_alerts_tools()
register_events_tools()
register_migrations_tools()
register_users_tools()
