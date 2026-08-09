"""MCP Transport abstraction — supports stdio (local) and HTTP (remote)."""

import asyncio
import json
import sys
from abc import ABC, abstractmethod
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.responses import JSONResponse

from .context import MCPContext
from .server import MCPServer
from .. import registry


class Transport(ABC):
    """Abstract transport for MCP protocol."""

    @abstractmethod
    async def run(self) -> None:
        """Run transport server."""
        pass


class StdioTransport(Transport):
    """Stdio transport (line-based JSON for local development)."""

    def __init__(self, server: MCPServer):
        """Initialize stdio transport.

        Args:
            server: MCPServer instance
        """
        self.server = server

    async def run(self) -> None:
        """Run stdio transport loop."""
        loop = asyncio.get_event_loop()

        while True:
            # Read line from stdin
            line = await loop.run_in_executor(None, sys.stdin.readline)
            if not line:
                break

            line = line.strip()
            if not line:
                continue

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
            response = await self.server.handle_request(request)

            # Send response
            print(json.dumps(response))
            sys.stdout.flush()


class HTTPTransport(Transport):
    """HTTP/SSE transport (for remote AgentOS)."""

    def __init__(self, server: MCPServer, port: int = 9500):
        """Initialize HTTP transport.

        Args:
            server: MCPServer instance
            port: Port to listen on
        """
        self.server = server
        self.port = port
        self.app = self._create_app()

    def _create_app(self) -> FastAPI:
        """Create FastAPI app for HTTP transport."""
        app = FastAPI(title="DEVPS MCP Server", version="1.0.0")

        @app.post("/mcp/call")
        async def mcp_call(
            request: dict[str, Any],
            authorization: Optional[str] = Header(None),
        ):
            """Call MCP tool via HTTP POST.

            Request body:
            {
              "method": "call_tool" | "list_tools",
              "params": {
                "name": "tool.name",
                "arguments": {...}
              }
            }

            Authorization: Bearer <token>
            """
            # Extract and validate token
            token = await self._extract_token(authorization)
            if not token:
                raise HTTPException(status_code=401, detail="Missing authorization")

            # Get user from token
            username = await self._validate_token(token)
            if not username:
                raise HTTPException(status_code=401, detail="Invalid token")

            # Update server context
            try:
                self.server.context = MCPContext.from_username(username)
            except ValueError:
                raise HTTPException(status_code=401, detail="User not found")

            # Handle request
            try:
                response = await self.server.handle_request(request)
                return JSONResponse(response)
            except Exception as e:
                return JSONResponse({
                    "success": False,
                    "error": str(e),
                }, status_code=500)

        @app.get("/mcp/health")
        async def health():
            """Health check endpoint."""
            return {"status": "ok"}

        return app

    async def _extract_token(self, authorization: Optional[str]) -> Optional[str]:
        """Extract Bearer token from Authorization header."""
        if not authorization:
            return None

        if not authorization.startswith("Bearer "):
            return None

        return authorization[7:]  # Remove "Bearer " prefix

    async def _validate_token(self, token: str) -> Optional[str]:
        """Validate token and return username.

        Token format: session cookie or MCP-specific JWT.
        For now, we accept session tokens.
        """
        # TODO: Implement token validation
        # Could be:
        # 1. Session cookie (decode and validate)
        # 2. JWT (verify signature)
        # 3. API key (lookup in database)

        # For now, return None (no validation)
        return None

    async def run(self) -> None:
        """Run HTTP transport server."""
        import uvicorn

        config = uvicorn.Config(
            self.app,
            host="0.0.0.0",
            port=self.port,
            log_level="info",
        )
        server = uvicorn.Server(config)
        await server.serve()


def get_transport(transport_type: str, mcp_server: MCPServer, **kwargs) -> Transport:
    """Factory function to create transport.

    Args:
        transport_type: "stdio" or "http"
        mcp_server: MCPServer instance
        **kwargs: Transport-specific arguments

    Returns:
        Transport instance
    """
    if transport_type == "stdio":
        return StdioTransport(mcp_server)
    elif transport_type == "http":
        port = kwargs.get("port", 9500)
        return HTTPTransport(mcp_server, port=port)
    else:
        raise ValueError(f"Unknown transport: {transport_type!r}")
