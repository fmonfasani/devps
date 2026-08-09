"""MCP Client for testing/demonstration.

Connects to MCP Server (stdio), sends requests, receives responses.
Useful for manual testing and demonstrations.
"""

import asyncio
import json
import subprocess
import sys
from typing import Any, Optional


class StdioMCPClient:
    """MCP Client that connects to server via stdio."""

    def __init__(self, server_process: subprocess.Popen):
        """Initialize client.

        Args:
            server_process: Running MCP server process
        """
        self.server_process = server_process

    async def call_tool(self, name: str, arguments: dict[str, Any] = None) -> dict[str, Any]:
        """Call a tool on the server.

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
        """List all available tools.

        Returns:
            Server response with tools list
        """
        request = {"method": "list_tools"}
        return await self._send_request(request)

    async def _send_request(self, request: dict[str, Any]) -> dict[str, Any]:
        """Send request to server and receive response.

        Args:
            request: Request dict

        Returns:
            Response dict
        """
        loop = asyncio.get_event_loop()

        # Send request
        request_json = json.dumps(request)
        await loop.run_in_executor(
            None,
            lambda: self.server_process.stdin.write((request_json + "\n").encode()),
        )
        await loop.run_in_executor(None, self.server_process.stdin.flush)

        # Receive response
        response_line = await loop.run_in_executor(
            None,
            self.server_process.stdout.readline,
        )

        if not response_line:
            raise RuntimeError("Server closed connection")

        return json.loads(response_line.decode().strip())

    async def close(self):
        """Close connection."""
        self.server_process.stdin.close()
        self.server_process.stdout.close()


async def main_interactive(authenticated_user: Optional[str] = None):
    """Run interactive MCP client.

    Args:
        authenticated_user: Optional authenticated username
    """
    # Start server
    cmd = [sys.executable, "-m", "devps_agent.mcp.server"]
    if authenticated_user:
        cmd.append(authenticated_user)

    server = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    client = StdioMCPClient(server)

    print("=" * 60)
    print(f"MCP Client connected (user: {authenticated_user or 'anonymous'})")
    print("=" * 60)

    try:
        # List tools
        print("\n📋 Listing available tools...")
        response = await client.list_tools()
        if response["success"]:
            tools = response["tools"]
            print(f"Found {len(tools)} tools:")
            for tool in tools:
                print(f"  - {tool['name']}: {tool['description']}")
        else:
            print(f"Error: {response.get('error')}")

        # Call projects.list
        print("\n🔧 Calling devps.projects.list...")
        response = await client.call_tool("devps.projects.list")
        print(f"Response: {json.dumps(response, indent=2)}")

        if response["success"]:
            result = json.loads(response["content"])
            projects = result.get("projects", [])
            print(f"Found {len(projects)} projects")

        await client.close()

    except Exception as e:
        print(f"Error: {e}")
        server.kill()
        raise


def manual_test():
    """Run manual test scenario."""
    print("Starting MCP Server manual test...\n")

    # Test 1: Anonymous mode
    print("Test 1: List tools (anonymous)")
    asyncio.run(main_interactive(authenticated_user=None))

    # Note: Test 2 would require actual users in the database
    # For now, this demonstrates the protocol flow


if __name__ == "__main__":
    manual_test()
