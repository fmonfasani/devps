"""MCP Server for DEVPS — implements Model Context Protocol over stdio.

Provides:
- Tool discovery (list_tools)
- Tool calling (call_tool)
- RBAC integration using existing rbac.py
"""

import asyncio
import json
import sys
from typing import Any, Optional

from .context import MCPContext
from .tools import TOOLS, list_tools as get_all_tools
from . import schemas
from .. import rbac


class MCPServer:
    """MCP Server implementation.

    Handles stdio protocol for tool discovery and execution.
    Uses DEVPS's existing RBAC for authorization.
    """

    def __init__(self, authenticated_user: Optional[str] = None):
        """Initialize MCP Server.

        Args:
            authenticated_user: Authenticated username for MCP context.
                               If None, server runs in anonymous mode (dev/testing).
        """
        self.authenticated_user = authenticated_user
        self.context = self._create_context()

    def _create_context(self) -> MCPContext:
        """Create MCP execution context."""
        if self.authenticated_user:
            try:
                return MCPContext.from_username(self.authenticated_user)
            except ValueError as e:
                raise RuntimeError(f"Invalid authenticated user: {e}") from e
        else:
            # Anonymous mode (for testing/development)
            return MCPContext.anonymous()

    async def handle_request(self, request: dict[str, Any]) -> dict[str, Any]:
        """Handle incoming MCP request.

        Supports:
        - {"method": "list_tools"}
        - {"method": "call_tool", "params": {"name": "...", "arguments": {...}}}

        Args:
            request: MCP request dict

        Returns:
            MCP response dict

        Raises:
            ValueError: If request is invalid
        """
        method = request.get("method")

        if method == "list_tools":
            return await self._list_tools_handler()

        elif method == "call_tool":
            params = request.get("params", {})
            return await self._call_tool_handler(
                params.get("name"),
                params.get("arguments", {})
            )

        else:
            return {
                "error": f"Unknown method: {method!r}",
                "success": False,
            }

    async def _list_tools_handler(self) -> dict[str, Any]:
        """Handle list_tools request.

        Returns list of available tool names with schemas.
        """
        try:
            tools = []
            for tool_name in get_all_tools():
                tools.append({
                    "name": tool_name,
                    "description": self._get_tool_description(tool_name),
                    "inputSchema": self._get_tool_schema(tool_name),
                })

            return {
                "success": True,
                "tools": tools,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    async def _call_tool_handler(self, tool_name: Optional[str], arguments: dict[str, Any]) -> dict[str, Any]:
        """Handle call_tool request.

        Validates tool name, checks RBAC, delegates to tool handler.
        """
        if not tool_name:
            return {
                "success": False,
                "error": "Tool name required",
            }

        # Get tool handler
        handler = TOOLS.get(tool_name)
        if not handler:
            return {
                "success": False,
                "error": f"Tool {tool_name!r} not found",
            }

        try:
            # Execute tool with context
            result = await handler(self.context, **arguments)

            return {
                "success": True,
                "content": json.dumps(result),
            }
        except rbac.RBACError as e:
            return {
                "success": False,
                "error": f"Authorization failed: {e}",
            }
        except ValueError as e:
            return {
                "success": False,
                "error": str(e),
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Tool execution failed: {e}",
            }

    @staticmethod
    def _get_tool_description(tool_name: str) -> str:
        """Get description for a tool."""
        descriptions = {
            # Projects
            "devps.projects.list": "List all projects accessible to the user",
            "devps.projects.get": "Get detailed information about a specific project",
            "devps.projects.delete": "Delete a project (admin only)",
            # Containers
            "devps.containers.status": "Get container status (running/dead/unhealthy)",
            "devps.containers.restart": "Restart a container",
            "devps.containers.logs": "Get container logs",
            # Health
            "devps.health.status": "Get health status of all projects",
            "devps.health.check": "Perform immediate health check on a project",
            # Alerts
            "devps.alerts.configure": "Configure email/Slack alerts for a project",
            "devps.alerts.mute": "Mute alerts temporarily (1-24 hours)",
            "devps.alerts.unmute": "Unmute alerts",
            # Events
            "devps.events.get": "Get events for a specific project",
            "devps.events.list": "Get global event log",
            # Migrations
            "devps.migrations.list": "List all migrations",
            "devps.migrations.transition": "Transition migration to next step",
            # Users
            "devps.users.list": "List all users (admin only)",
            "devps.users.create": "Create a new user (admin only)",
            "devps.users.update-role": "Update user role (admin only)",
            "devps.users.delete": "Delete a user (admin only)",
        }
        return descriptions.get(tool_name, "")

    @staticmethod
    def _get_tool_schema(tool_name: str) -> dict[str, Any]:
        """Get input schema for a tool."""
        schemas_map = {
            # Projects
            "devps.projects.list": {
                "type": "object",
                "properties": {
                    "filter_owner": {"type": "string", "description": "Filter by project owner"},
                    "filter_status": {"type": "string", "description": "Filter by status"},
                },
            },
            "devps.projects.get": {
                "type": "object",
                "properties": {"name": {"type": "string", "description": "Project name"}},
                "required": ["name"],
            },
            "devps.projects.delete": {
                "type": "object",
                "properties": {"name": {"type": "string", "description": "Project name"}},
                "required": ["name"],
            },
            # Containers
            "devps.containers.status": {
                "type": "object",
                "properties": {"project_name": {"type": "string"}},
                "required": ["project_name"],
            },
            "devps.containers.restart": {
                "type": "object",
                "properties": {"project_name": {"type": "string"}},
                "required": ["project_name"],
            },
            "devps.containers.logs": {
                "type": "object",
                "properties": {
                    "project_name": {"type": "string"},
                    "tail": {"type": "integer", "description": "Number of lines (10-1000, default 200)"},
                },
                "required": ["project_name"],
            },
            # Health
            "devps.health.status": {"type": "object", "properties": {}},
            "devps.health.check": {
                "type": "object",
                "properties": {"project_name": {"type": "string"}},
                "required": ["project_name"],
            },
            # Alerts
            "devps.alerts.configure": {
                "type": "object",
                "properties": {
                    "project_name": {"type": "string"},
                    "email": {"type": "string"},
                    "slack": {"type": "string"},
                    "enabled": {"type": "boolean"},
                },
                "required": ["project_name"],
            },
            "devps.alerts.mute": {
                "type": "object",
                "properties": {
                    "project_name": {"type": "string"},
                    "hours": {"type": "integer", "description": "1-24 hours"},
                },
                "required": ["project_name", "hours"],
            },
            "devps.alerts.unmute": {
                "type": "object",
                "properties": {"project_name": {"type": "string"}},
                "required": ["project_name"],
            },
            # Events
            "devps.events.get": {
                "type": "object",
                "properties": {
                    "project_name": {"type": "string"},
                    "limit": {"type": "integer", "description": "Default 100"},
                },
                "required": ["project_name"],
            },
            "devps.events.list": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "description": "Default 200"}},
            },
            # Migrations
            "devps.migrations.list": {"type": "object", "properties": {}},
            "devps.migrations.transition": {
                "type": "object",
                "properties": {
                    "project_name": {"type": "string"},
                    "step": {"type": "string", "description": "paralleled|cutover|decommissioned"},
                    "source_description": {"type": "string"},
                },
                "required": ["project_name", "step"],
            },
            # Users
            "devps.users.list": {"type": "object", "properties": {}},
            "devps.users.create": {
                "type": "object",
                "properties": {
                    "username": {"type": "string"},
                    "password": {"type": "string"},
                    "role": {"type": "string", "description": "admin|deployer|viewer"},
                },
                "required": ["username", "password"],
            },
            "devps.users.update-role": {
                "type": "object",
                "properties": {
                    "username": {"type": "string"},
                    "role": {"type": "string", "description": "admin|deployer|viewer"},
                },
                "required": ["username", "role"],
            },
            "devps.users.delete": {
                "type": "object",
                "properties": {"username": {"type": "string"}},
                "required": ["username"],
            },
        }
        return schemas_map.get(tool_name, {})


async def stdio_server_loop(server: MCPServer) -> None:
    """Run MCP server in stdio mode.

    Reads JSON-encoded requests from stdin, writes responses to stdout.
    One request per line (jsonl format).
    """
    loop = asyncio.get_event_loop()

    while True:
        # Read line from stdin
        line = await loop.run_in_executor(None, sys.stdin.readline)
        if not line:
            break  # EOF

        line = line.strip()
        if not line:
            continue  # Empty line

        try:
            request = json.loads(line)
        except json.JSONDecodeError as e:
            response = {
                "error": f"Invalid JSON: {e}",
                "success": False,
            }
            print(json.dumps(response))
            continue

        # Handle request
        response = await server.handle_request(request)

        # Send response
        print(json.dumps(response))
        sys.stdout.flush()


def main(authenticated_user: Optional[str] = None) -> None:
    """Run MCP Server in stdio mode.

    Args:
        authenticated_user: Optional authenticated username for RBAC context
    """
    server = MCPServer(authenticated_user=authenticated_user)
    asyncio.run(stdio_server_loop(server))


if __name__ == "__main__":
    import sys
    authenticated_user = sys.argv[1] if len(sys.argv) > 1 else None
    main(authenticated_user=authenticated_user)
