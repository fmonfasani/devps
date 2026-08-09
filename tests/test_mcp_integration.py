"""Integration tests for MCP Server.

Tests the full flow: request → server → tool → registry → response.
"""

import json
import pytest
from unittest.mock import patch

from devps_agent.mcp.server import MCPServer
from devps_agent import rbac


class TestMCPIntegration:
    """Integration tests."""

    @pytest.mark.asyncio
    async def test_full_flow_list_projects_as_admin(self):
        """Full flow: admin lists projects."""
        with patch('devps_agent.registry.get_user') as mock_get_user, \
             patch('devps_agent.registry.list_projects') as mock_list_projects:

            # Setup
            mock_get_user.return_value = {
                "username": "admin@example.com",
                "role": "admin",
                "created_at": "2026-01-01T00:00:00Z",
            }

            mock_list_projects.return_value = [
                {
                    "name": "test-app",
                    "managed_by": "devps",
                    "repo_url": "https://github.com/user/test-app",
                    "git_ref": "main",
                    "git_sha": "abc123",
                    "domain": "test-app.example.com",
                    "status": "deployed",
                    "health_status": "running",
                    "restart_count": 0,
                    "owner": "admin@example.com",
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-01-01T00:00:00Z",
                    "ports": [
                        {
                            "service": "web",
                            "host_port": 40001,
                            "container_port": 3000,
                        }
                    ],
                    "last_event": {
                        "kind": "deploy",
                        "success": True,
                        "created_at": "2026-01-01T00:00:00Z",
                    },
                },
            ]

            # Execute
            server = MCPServer(authenticated_user="admin@example.com")

            response = await server.handle_request({
                "method": "call_tool",
                "params": {
                    "name": "devps.projects.list",
                    "arguments": {},
                }
            })

            # Verify
            assert response["success"] is True

            result = json.loads(response["content"])
            assert "projects" in result
            assert len(result["projects"]) == 1

            project = result["projects"][0]
            assert project["name"] == "test-app"
            assert project["status"] == "deployed"
            assert project["owner"] == "admin@example.com"

    @pytest.mark.asyncio
    async def test_full_flow_get_project_as_deployer(self):
        """Full flow: deployer gets own project."""
        with patch('devps_agent.registry.get_user') as mock_get_user, \
             patch('devps_agent.registry.get_project') as mock_get_project:

            # Setup
            mock_get_user.return_value = {
                "username": "dev@example.com",
                "role": "deployer",
            }

            mock_get_project.return_value = {
                "name": "my-app",
                "managed_by": "devps",
                "repo_url": "https://github.com/dev/my-app",
                "git_ref": "main",
                "git_sha": "def456",
                "domain": "my-app.example.com",
                "status": "deployed",
                "health_status": "running",
                "restart_count": 1,
                "owner": "dev@example.com",
                "created_at": "2026-01-05T00:00:00Z",
                "updated_at": "2026-01-05T10:00:00Z",
                "ports": [
                    {
                        "service": "web",
                        "host_port": 40002,
                        "container_port": 8080,
                    }
                ],
                "last_event": {
                    "kind": "manual_restart",
                    "success": True,
                    "created_at": "2026-01-05T10:00:00Z",
                },
            }

            # Execute
            server = MCPServer(authenticated_user="dev@example.com")

            response = await server.handle_request({
                "method": "call_tool",
                "params": {
                    "name": "devps.projects.get",
                    "arguments": {"name": "my-app"},
                }
            })

            # Verify
            assert response["success"] is True

            result = json.loads(response["content"])
            assert "project" in result

            project = result["project"]
            assert project["name"] == "my-app"
            assert project["owner"] == "dev@example.com"
            assert project["restart_count"] == 1

    @pytest.mark.asyncio
    async def test_rbac_deployer_cannot_access_others_project(self):
        """Deployer cannot get another user's project."""
        with patch('devps_agent.registry.get_user') as mock_get_user, \
             patch('devps_agent.registry.get_project') as mock_get_project:

            # Setup
            mock_get_user.return_value = {
                "username": "dev1@example.com",
                "role": "deployer",
            }

            mock_get_project.return_value = {
                "name": "other-app",
                "owner": "dev2@example.com",  # Different owner
                "status": "deployed",
            }

            # Execute
            server = MCPServer(authenticated_user="dev1@example.com")

            response = await server.handle_request({
                "method": "call_tool",
                "params": {
                    "name": "devps.projects.get",
                    "arguments": {"name": "other-app"},
                }
            })

            # Verify — should fail because deployer doesn't own the project
            assert response["success"] is False
            assert "Authorization failed" in response.get("error", "")

    @pytest.mark.asyncio
    async def test_viewer_can_list_projects(self):
        """Viewer can list all projects (read-only)."""
        with patch('devps_agent.registry.get_user') as mock_get_user, \
             patch('devps_agent.registry.list_projects') as mock_list_projects:

            mock_get_user.return_value = {
                "username": "viewer@example.com",
                "role": "viewer",
            }

            mock_list_projects.return_value = [
                {"name": "app1", "owner": "admin@example.com"},
                {"name": "app2", "owner": "dev@example.com"},
            ]

            server = MCPServer(authenticated_user="viewer@example.com")

            response = await server.handle_request({
                "method": "call_tool",
                "params": {
                    "name": "devps.projects.list",
                    "arguments": {},
                }
            })

            assert response["success"] is True
            result = json.loads(response["content"])
            assert len(result["projects"]) == 2  # Viewer sees all

    @pytest.mark.asyncio
    async def test_tool_discovery_returns_complete_info(self):
        """Tool discovery returns name, description, and schema."""
        server = MCPServer(authenticated_user=None)

        response = await server.handle_request({"method": "list_tools"})

        assert response["success"] is True

        # Check devps.projects.list tool
        tools_list = {t["name"]: t for t in response["tools"]}
        assert "devps.projects.list" in tools_list

        tool = tools_list["devps.projects.list"]
        assert "description" in tool
        assert len(tool["description"]) > 0
        assert "inputSchema" in tool
        assert "type" in tool["inputSchema"]

    @pytest.mark.asyncio
    async def test_project_not_found_error(self):
        """Getting nonexistent project returns appropriate error."""
        with patch('devps_agent.registry.get_user') as mock_get_user, \
             patch('devps_agent.registry.get_project') as mock_get_project:

            mock_get_user.return_value = {
                "username": "admin@example.com",
                "role": "admin",
            }

            mock_get_project.return_value = None  # Project not found

            server = MCPServer(authenticated_user="admin@example.com")

            response = await server.handle_request({
                "method": "call_tool",
                "params": {
                    "name": "devps.projects.get",
                    "arguments": {"name": "nonexistent"},
                }
            })

            assert response["success"] is False
            assert "not found" in response.get("error", "").lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
