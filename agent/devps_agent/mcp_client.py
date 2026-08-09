"""
MCP Client for AgentOS

Allows AgentOS to consume its own MCP Server capabilities as tools.
Use this when AgentOS needs to interact with itself or other MCP servers.

Example:
    client = DevpsMCPClient()
    logs = await client.call_tool("get_logs", {"project_name": "my-app"})
    health = await client.read_resource("devps://health")
"""

import asyncio
import json
import subprocess
import sys
from typing import Any

from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client


class DevpsMCPClient:
    """Client for interacting with devps MCP Server."""

    def __init__(self, server_command: str = None):
        """Initialize the MCP client.

        Args:
            server_command: Command to start the MCP server
                          (default: python -m devps_agent.mcp_server)
        """
        self.server_command = server_command or [
            sys.executable,
            "-m",
            "devps_agent.mcp_server"
        ]
        self.session = None

    async def connect(self):
        """Connect to the MCP server."""
        if self.session is None:
            self.session = ClientSession(
                stdio_client(self.server_command)
            )
            await self.session.__aenter__()

    async def disconnect(self):
        """Disconnect from the MCP server."""
        if self.session:
            await self.session.__aexit__(None, None, None)
            self.session = None

    async def call_tool(self, name: str, arguments: dict) -> dict:
        """Call a tool on the MCP server.

        Args:
            name: Tool name
            arguments: Tool arguments

        Returns:
            Tool result
        """
        await self.connect()
        result = await self.session.call_tool(name, arguments)
        return {
            "success": not result.isError,
            "content": result.content[0].text if result.content else "",
            "error": result.content[0].text if result.isError else None
        }

    async def read_resource(self, uri: str) -> str:
        """Read a resource from the MCP server.

        Args:
            uri: Resource URI (e.g., "devps://projects")

        Returns:
            Resource content
        """
        await self.connect()
        resource = await self.session.read_resource(uri)
        return resource.contents[0].text if resource.contents else ""

    async def list_tools(self) -> list[dict]:
        """List available tools."""
        await self.connect()
        tools = await self.session.list_tools()
        return [
            {
                "name": t.name,
                "description": t.description,
                "inputSchema": t.inputSchema
            }
            for t in tools.tools
        ]

    async def list_resources(self) -> list[dict]:
        """List available resources."""
        await self.connect()
        resources = await self.session.list_resources()
        return [
            {
                "name": r.name,
                "description": r.description,
                "uri_template": getattr(r, "uriTemplate", r.name)
            }
            for r in resources.resources
        ]

    # Convenience methods
    async def list_projects(self, owner: str = None) -> list[dict]:
        """List all projects."""
        result = await self.call_tool("list_projects", {"owner": owner} if owner else {})
        if result["success"]:
            return json.loads(result["content"])
        return []

    async def get_project(self, project_name: str) -> dict:
        """Get project details."""
        result = await self.call_tool("get_project", {"project_name": project_name})
        if result["success"]:
            return json.loads(result["content"])
        return {}

    async def get_logs(self, project_name: str, tail: int = 100, filter_type: str = "all") -> str:
        """Get project logs."""
        result = await self.call_tool("get_logs", {
            "project_name": project_name,
            "tail": tail,
            "filter": filter_type
        })
        return result["content"]

    async def get_health_status(self) -> dict:
        """Get health status of all projects."""
        result = await self.call_tool("get_health_status", {})
        if result["success"]:
            return json.loads(result["content"])
        return {}

    async def restart_project(self, project_name: str) -> bool:
        """Restart a project."""
        result = await self.call_tool("restart_project", {"project_name": project_name})
        return result["success"]

    async def mute_alerts(self, project_name: str, hours: int) -> bool:
        """Mute alerts for a project."""
        result = await self.call_tool("mute_alerts", {
            "project_name": project_name,
            "hours": hours
        })
        return result["success"]

    async def list_users(self) -> list[dict]:
        """List all users."""
        result = await self.call_tool("list_users", {})
        if result["success"]:
            return json.loads(result["content"])
        return []

    async def get_migrations(self) -> list[dict]:
        """Get ongoing migrations."""
        result = await self.call_tool("get_migrations", {})
        if result["success"]:
            return json.loads(result["content"])
        return []

    async def __aenter__(self):
        """Context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        await self.disconnect()


# Example usage
async def example_usage():
    """Example of using the MCP client."""
    async with DevpsMCPClient() as client:
        # List projects
        print("Projects:")
        projects = await client.list_projects()
        for p in projects:
            print(f"  - {p['name']}: {p.get('status', 'unknown')}")

        # Check health
        print("\nHealth status:")
        health = await client.get_health_status()
        for h in health:
            print(f"  - {h['name']}: {h.get('status', 'unknown')}")

        # Get specific project logs
        if projects:
            project_name = projects[0]["name"]
            print(f"\nLogs for {project_name}:")
            logs = await client.get_logs(project_name, tail=50)
            print(logs[:500] + "..." if len(logs) > 500 else logs)


if __name__ == "__main__":
    asyncio.run(example_usage())
