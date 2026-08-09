"""HTTP MCP Client for remote connections.

Allows external tools (AgentOS, etc) to connect to DEVPS MCP Server via HTTP.
"""

import httpx
import json
from typing import Any, Optional


class HTTPMCPClient:
    """HTTP client for MCP Server."""

    def __init__(self, base_url: str, token: Optional[str] = None):
        """Initialize HTTP client.

        Args:
            base_url: Base URL of MCP Server (e.g., "https://devps.example.com")
            token: Bearer token for authentication
        """
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.client = httpx.AsyncClient(base_url=self.base_url)

    async def call_tool(self, name: str, arguments: dict[str, Any] = None) -> dict[str, Any]:
        """Call a tool on the remote server.

        Args:
            name: Tool name
            arguments: Tool arguments

        Returns:
            Server response
        """
        arguments = arguments or {}

        request = {
            "method": "call_tool",
            "params": {
                "name": name,
                "arguments": arguments,
            }
        }

        return await self._send_request(request)

    async def list_tools(self) -> dict[str, Any]:
        """List all available tools on the remote server.

        Returns:
            Server response with tools list
        """
        request = {"method": "list_tools"}
        return await self._send_request(request)

    async def _send_request(self, request: dict[str, Any]) -> dict[str, Any]:
        """Send request to remote server.

        Args:
            request: Request dict

        Returns:
            Response dict
        """
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        response = await self.client.post(
            "/mcp/call",
            json=request,
            headers=headers,
        )

        response.raise_for_status()
        return response.json()

    async def close(self):
        """Close connection."""
        await self.client.aclose()


async def example_usage():
    """Example usage of HTTP MCP Client."""
    # Connect to remote server
    client = HTTPMCPClient(
        base_url="https://devps.example.com",
        token="your-bearer-token",
    )

    try:
        # List tools
        print("Listing tools...")
        response = await client.list_tools()
        if response["success"]:
            tools = response["tools"]
            print(f"Found {len(tools)} tools:")
            for tool in tools:
                print(f"  - {tool['name']}")

        # Call tool
        print("\nCalling devps.projects.list...")
        response = await client.call_tool("devps.projects.list")
        if response["success"]:
            result = json.loads(response["content"])
            projects = result.get("projects", [])
            print(f"Found {len(projects)} projects")

    finally:
        await client.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(example_usage())
