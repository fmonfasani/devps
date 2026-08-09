"""Tests for MCP Server — Phase 1.

Tests:
- Tool discovery
- Tool execution
- RBAC integration
- Error handling
"""

import pytest
import json
from unittest.mock import patch, MagicMock

from devps_agent.mcp.server import MCPServer
from devps_agent.mcp.context import MCPContext
from devps_agent import rbac


class TestMCPServer:
    """MCP Server tests."""

    def test_server_initialization_anonymous(self):
        """Server can be initialized in anonymous mode (for dev/testing)."""
        server = MCPServer(authenticated_user=None)
        assert server.context.is_authenticated() is False

    def test_server_initialization_authenticated(self):
        """Server can be initialized with authenticated user."""
        with patch('devps_agent.registry.get_user') as mock_get_user:
            mock_get_user.return_value = {
                "username": "admin@example.com",
                "role": "admin",
            }

            server = MCPServer(authenticated_user="admin@example.com")
            assert server.context.is_authenticated() is True
            assert server.context.username == "admin@example.com"

    def test_server_initialization_invalid_user(self):
        """Server initialization fails if user doesn't exist."""
        with patch('devps_agent.registry.get_user') as mock_get_user:
            mock_get_user.return_value = None

            with pytest.raises(RuntimeError, match="Invalid authenticated user"):
                MCPServer(authenticated_user="nonexistent@example.com")

    @pytest.mark.asyncio
    async def test_list_tools(self):
        """Server can list available tools."""
        server = MCPServer(authenticated_user=None)

        response = await server.handle_request({"method": "list_tools"})

        assert response["success"] is True
        assert "tools" in response
        assert len(response["tools"]) >= 2  # At least 2 Phase 1 tools

        tool_names = [t["name"] for t in response["tools"]]
        assert "devps.projects.list" in tool_names
        assert "devps.projects.get" in tool_names

    @pytest.mark.asyncio
    async def test_list_tools_includes_schema(self):
        """Listed tools include input schemas."""
        server = MCPServer(authenticated_user=None)

        response = await server.handle_request({"method": "list_tools"})

        assert response["success"] is True

        # Find projects.list tool
        projects_list = next(
            (t for t in response["tools"] if t["name"] == "devps.projects.list"),
            None
        )
        assert projects_list is not None
        assert "inputSchema" in projects_list
        assert "description" in projects_list

    @pytest.mark.asyncio
    async def test_call_tool_list_projects_anonymous(self):
        """Tool execution fails if RBAC check fails."""
        server = MCPServer(authenticated_user=None)

        response = await server.handle_request({
            "method": "call_tool",
            "params": {
                "name": "devps.projects.list",
                "arguments": {},
            }
        })

        assert response["success"] is False
        assert "Authorization failed" in response.get("error", "")

    @pytest.mark.asyncio
    async def test_call_tool_list_projects_admin(self):
        """Admin can list all projects."""
        with patch('devps_agent.registry.get_user') as mock_get_user, \
             patch('devps_agent.registry.list_projects') as mock_list_projects:

            mock_get_user.return_value = {
                "username": "admin@example.com",
                "role": "admin",
            }

            mock_list_projects.return_value = [
                {"name": "project1", "owner": "admin@example.com", "status": "deployed"},
                {"name": "project2", "owner": "user@example.com", "status": "deployed"},
            ]

            server = MCPServer(authenticated_user="admin@example.com")

            response = await server.handle_request({
                "method": "call_tool",
                "params": {
                    "name": "devps.projects.list",
                    "arguments": {},
                }
            })

            assert response["success"] is True
            result = json.loads(response["content"])
            assert len(result["projects"]) == 2

    @pytest.mark.asyncio
    async def test_call_tool_list_projects_deployer(self):
        """Deployer can only list their own projects."""
        with patch('devps_agent.registry.get_user') as mock_get_user, \
             patch('devps_agent.registry.list_projects') as mock_list_projects:

            mock_get_user.return_value = {
                "username": "dev@example.com",
                "role": "deployer",
            }

            mock_list_projects.return_value = [
                {"name": "project1", "owner": "dev@example.com", "status": "deployed"},
                {"name": "project2", "owner": "other@example.com", "status": "deployed"},
            ]

            server = MCPServer(authenticated_user="dev@example.com")

            response = await server.handle_request({
                "method": "call_tool",
                "params": {
                    "name": "devps.projects.list",
                    "arguments": {},
                }
            })

            assert response["success"] is True
            result = json.loads(response["content"])
            assert len(result["projects"]) == 1
            assert result["projects"][0]["owner"] == "dev@example.com"

    @pytest.mark.asyncio
    async def test_call_tool_get_project(self):
        """Can get project details with proper permissions."""
        with patch('devps_agent.registry.get_user') as mock_get_user, \
             patch('devps_agent.registry.get_project') as mock_get_project:

            mock_get_user.return_value = {
                "username": "admin@example.com",
                "role": "admin",
            }

            mock_get_project.return_value = {
                "name": "my-app",
                "owner": "admin@example.com",
                "status": "deployed",
                "ports": [],
                "last_event": None,
            }

            server = MCPServer(authenticated_user="admin@example.com")

            response = await server.handle_request({
                "method": "call_tool",
                "params": {
                    "name": "devps.projects.get",
                    "arguments": {"name": "my-app"},
                }
            })

            assert response["success"] is True
            result = json.loads(response["content"])
            assert result["project"]["name"] == "my-app"

    @pytest.mark.asyncio
    async def test_call_tool_missing_required_argument(self):
        """Tool execution fails if required argument is missing."""
        with patch('devps_agent.registry.get_user') as mock_get_user:
            mock_get_user.return_value = {
                "username": "admin@example.com",
                "role": "admin",
            }

            server = MCPServer(authenticated_user="admin@example.com")

            response = await server.handle_request({
                "method": "call_tool",
                "params": {
                    "name": "devps.projects.get",
                    "arguments": {},  # Missing 'name' argument
                }
            })

            assert response["success"] is False
            assert "error" in response

    @pytest.mark.asyncio
    async def test_call_tool_nonexistent(self):
        """Calling nonexistent tool returns error."""
        server = MCPServer(authenticated_user=None)

        response = await server.handle_request({
            "method": "call_tool",
            "params": {
                "name": "devps.nonexistent.tool",
                "arguments": {},
            }
        })

        assert response["success"] is False
        assert "not found" in response.get("error", "").lower()

    @pytest.mark.asyncio
    async def test_invalid_request_method(self):
        """Invalid method returns error."""
        server = MCPServer(authenticated_user=None)

        response = await server.handle_request({"method": "invalid_method"})

        assert response["success"] is False
        assert "Unknown method" in response.get("error", "")

    @pytest.mark.asyncio
    async def test_malformed_request(self):
        """Malformed request is handled gracefully."""
        server = MCPServer(authenticated_user=None)

        response = await server.handle_request({})  # Missing 'method'

        assert response["success"] is False


class TestMCPContext:
    """MCP Context tests."""

    def test_context_anonymous(self):
        """Anonymous context has no user."""
        context = MCPContext.anonymous()
        assert context.is_authenticated() is False

    def test_context_from_username(self):
        """Context can be created from username."""
        with patch('devps_agent.registry.get_user') as mock_get_user:
            mock_get_user.return_value = {
                "username": "test@example.com",
                "role": "viewer",
            }

            context = MCPContext.from_username("test@example.com")
            assert context.is_authenticated() is True
            assert context.username == "test@example.com"

    def test_context_from_username_not_found(self):
        """Context creation fails if user doesn't exist."""
        with patch('devps_agent.registry.get_user') as mock_get_user:
            mock_get_user.return_value = None

            with pytest.raises(ValueError):
                MCPContext.from_username("nonexistent@example.com")

    def test_require_permission_not_authenticated(self):
        """Permission check fails if not authenticated."""
        context = MCPContext.anonymous()

        with pytest.raises(rbac.RBACError, match="Not authenticated"):
            context.require_permission("list_projects")

    def test_require_permission_success(self):
        """Permission check succeeds with valid role."""
        with patch('devps_agent.registry.get_user') as mock_get_user, \
             patch('devps_agent.rbac.require_permission') as mock_require:

            mock_get_user.return_value = {
                "username": "admin@example.com",
                "role": "admin",
            }

            context = MCPContext.from_username("admin@example.com")
            context.require_permission("list_projects")

            mock_require.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
