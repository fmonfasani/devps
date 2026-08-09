"""
MCP Server for AgentOS/devps

Exposes all operational capabilities via the Model Context Protocol:
- Project management (create, list, delete, restart, etc)
- Health monitoring (status, logs, events)
- User management (create, list, update roles)
- Deployments (deploy, rollback, status)
- Alerts (configure, mute, unmute)
"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.types import (
    Tool,
    TextContent,
    ToolResult,
    Resource,
    ResourceTemplate,
)

from . import config, docker_ops, registry
from .db import connect

server = Server("devps-agent")


# ============================================================================
# TOOLS - Project Management
# ============================================================================

@server.list_tools()
async def list_tools() -> list[Tool]:
    """List all available tools."""
    return [
        # Projects
        Tool(
            name="list_projects",
            description="List all projects with their status",
            inputSchema={
                "type": "object",
                "properties": {
                    "owner": {
                        "type": "string",
                        "description": "Filter by project owner (optional)"
                    }
                }
            }
        ),
        Tool(
            name="get_project",
            description="Get detailed info about a specific project",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {"type": "string", "description": "Project name"}
                },
                "required": ["project_name"]
            }
        ),
        Tool(
            name="create_project",
            description="Create a new project (auto-generates GitHub repo + deploys)",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {"type": "string", "description": "Project name"},
                    "domain": {"type": "string", "description": "Domain (optional)"},
                },
                "required": ["project_name"]
            }
        ),
        Tool(
            name="restart_project",
            description="Restart a running project's container",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {"type": "string", "description": "Project name"}
                },
                "required": ["project_name"]
            }
        ),
        Tool(
            name="stop_project",
            description="Stop a running project",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {"type": "string", "description": "Project name"}
                },
                "required": ["project_name"]
            }
        ),

        # Logs & Debugging
        Tool(
            name="get_logs",
            description="Get container logs for a project",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {"type": "string", "description": "Project name"},
                    "tail": {
                        "type": "integer",
                        "description": "Number of lines to fetch (default: 100)"
                    },
                    "filter": {
                        "type": "string",
                        "description": "Filter by level: all/error/warn (default: all)"
                    }
                },
                "required": ["project_name"]
            }
        ),
        Tool(
            name="get_events",
            description="Get recent events for a project",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {"type": "string", "description": "Project name"},
                    "limit": {
                        "type": "integer",
                        "description": "Number of events to fetch (default: 10)"
                    }
                },
                "required": ["project_name"]
            }
        ),

        # Health Monitoring
        Tool(
            name="get_health_status",
            description="Get health status of all projects",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="get_project_health",
            description="Get detailed health info for a project",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {"type": "string", "description": "Project name"}
                },
                "required": ["project_name"]
            }
        ),

        # Alerts
        Tool(
            name="configure_alerts",
            description="Configure alerts for a project",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {"type": "string"},
                    "email": {"type": "string", "description": "Alert email"},
                    "slack": {"type": "string", "description": "Slack webhook URL"},
                    "enabled": {"type": "boolean"}
                },
                "required": ["project_name", "enabled"]
            }
        ),
        Tool(
            name="mute_alerts",
            description="Mute alerts for a project temporarily",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {"type": "string"},
                    "hours": {
                        "type": "integer",
                        "description": "Hours to mute (1-24)"
                    }
                },
                "required": ["project_name", "hours"]
            }
        ),

        # Users
        Tool(
            name="list_users",
            description="List all users",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="create_user",
            description="Create a new user",
            inputSchema={
                "type": "object",
                "properties": {
                    "username": {"type": "string"},
                    "password": {"type": "string"},
                    "role": {"type": "string", "enum": ["admin", "deployer", "viewer"]}
                },
                "required": ["username", "password", "role"]
            }
        ),
        Tool(
            name="update_user_role",
            description="Update user role",
            inputSchema={
                "type": "object",
                "properties": {
                    "username": {"type": "string"},
                    "role": {"type": "string", "enum": ["admin", "deployer", "viewer"]}
                },
                "required": ["username", "role"]
            }
        ),

        # Deployments
        Tool(
            name="deploy_project",
            description="Deploy a project from GitHub",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {"type": "string"},
                    "repo_url": {"type": "string"},
                    "git_ref": {"type": "string", "description": "Git branch/tag"},
                    "domain": {"type": "string", "description": "Domain (optional)"},
                },
                "required": ["project_name", "repo_url"]
            }
        ),
        Tool(
            name="get_migrations",
            description="List ongoing project migrations",
            inputSchema={"type": "object", "properties": {}}
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> ToolResult:
    """Execute a tool."""
    try:
        if name == "list_projects":
            projects = registry.list_projects()
            owner = arguments.get("owner")
            if owner:
                projects = [p for p in projects if p.get("owner") == owner]
            return ToolResult(
                content=[TextContent(type="text", text=json.dumps(projects, indent=2))]
            )

        elif name == "get_project":
            project = registry.get_project(arguments["project_name"])
            if not project:
                return ToolResult(
                    content=[TextContent(type="text", text="Project not found")],
                    isError=True
                )
            return ToolResult(
                content=[TextContent(type="text", text=json.dumps(project, indent=2))]
            )

        elif name == "get_logs":
            project_name = arguments["project_name"]
            tail = arguments.get("tail", 100)
            logs = docker_ops.container_logs(project_name, tail)

            filter_type = arguments.get("filter", "all")
            if filter_type == "error":
                logs = "\n".join(l for l in logs.split("\n") if "error" in l.lower())
            elif filter_type == "warn":
                logs = "\n".join(l for l in logs.split("\n") if "warn" in l.lower())

            return ToolResult(
                content=[TextContent(type="text", text=logs)]
            )

        elif name == "get_events":
            project_name = arguments["project_name"]
            limit = arguments.get("limit", 10)
            events = registry.get_events(project_name, limit)
            return ToolResult(
                content=[TextContent(type="text", text=json.dumps(events, indent=2))]
            )

        elif name == "get_health_status":
            from .routers.health_status import list_health
            health = list_health()
            return ToolResult(
                content=[TextContent(type="text", text=json.dumps(health, indent=2))]
            )

        elif name == "get_project_health":
            project_name = arguments["project_name"]
            project = registry.get_project(project_name)
            if not project:
                return ToolResult(
                    content=[TextContent(type="text", text="Project not found")],
                    isError=True
                )
            health_info = {
                "name": project_name,
                "status": project.get("health_status"),
                "restart_count": project.get("restart_count"),
                "last_check_at": project.get("last_health_check_at"),
                "last_restart_at": project.get("last_restart_at"),
                "domain": project.get("domain"),
                "ports": project.get("ports")
            }
            return ToolResult(
                content=[TextContent(type="text", text=json.dumps(health_info, indent=2))]
            )

        elif name == "restart_project":
            project_name = arguments["project_name"]
            project = registry.get_project(project_name)
            if not project:
                return ToolResult(
                    content=[TextContent(type="text", text="Project not found")],
                    isError=True
                )

            project_dir = Path(config.PROJECTS_DIR) / project_name
            docker_ops.compose_restart(project_dir, "docker-compose.yml")

            with connect() as conn:
                conn.execute(
                    "INSERT INTO events (project_name, kind, detail, success, created_at) VALUES (?, ?, ?, ?, ?)",
                    (project_name, "manual_restart", "Restarted via MCP", 1, datetime.utcnow().isoformat() + "Z")
                )

            return ToolResult(
                content=[TextContent(type="text", text=f"Project {project_name} restarted")]
            )

        elif name == "list_users":
            users = registry.list_users()
            return ToolResult(
                content=[TextContent(type="text", text=json.dumps(users, indent=2))]
            )

        elif name == "get_migrations":
            migrations = registry.list_migrations()
            return ToolResult(
                content=[TextContent(type="text", text=json.dumps(migrations, indent=2))]
            )

        else:
            return ToolResult(
                content=[TextContent(type="text", text=f"Unknown tool: {name}")],
                isError=True
            )

    except Exception as e:
        return ToolResult(
            content=[TextContent(type="text", text=f"Error: {str(e)}")],
            isError=True
        )


# ============================================================================
# RESOURCES - Project & Log streaming
# ============================================================================

@server.list_resources()
async def list_resources() -> list[Resource | ResourceTemplate]:
    """List all available resources."""
    projects = registry.list_projects()

    resources = [
        ResourceTemplate(
            uriTemplate="devps://projects",
            name="All Projects",
            description="List all projects and their status",
            mimeType="application/json"
        ),
        ResourceTemplate(
            uriTemplate="devps://project/{project_name}",
            name="Project Details",
            description="Get details about a specific project",
            mimeType="application/json"
        ),
        ResourceTemplate(
            uriTemplate="devps://project/{project_name}/logs",
            name="Project Logs",
            description="Get live logs from a project container",
            mimeType="text/plain"
        ),
        ResourceTemplate(
            uriTemplate="devps://health",
            name="Health Status",
            description="Real-time health status of all projects",
            mimeType="application/json"
        ),
    ]

    return resources


@server.read_resource()
async def read_resource(uri: str) -> str:
    """Read a resource."""
    if uri == "devps://projects":
        projects = registry.list_projects()
        return json.dumps(projects, indent=2)

    elif uri.startswith("devps://project/"):
        project_name = uri.replace("devps://project/", "").split("/")[0]
        project = registry.get_project(project_name)
        if not project:
            return json.dumps({"error": "Project not found"})
        return json.dumps(project, indent=2)

    elif uri.endswith("/logs"):
        project_name = uri.replace("devps://project/", "").replace("/logs", "")
        logs = docker_ops.container_logs(project_name, 200)
        return logs

    elif uri == "devps://health":
        from .routers.health_status import list_health
        health = list_health()
        return json.dumps(health, indent=2)

    else:
        return json.dumps({"error": "Unknown resource"})


# ============================================================================
# PROMPTS - Common operations
# ============================================================================

@server.list_prompts()
async def list_prompts() -> list[dict]:
    """List common operation prompts."""
    return [
        {
            "name": "deploy_project",
            "description": "Deploy a new project from GitHub",
            "arguments": [
                {"name": "project_name", "description": "Name for the new project"},
                {"name": "repo_url", "description": "GitHub repository URL"},
                {"name": "domain", "description": "Optional domain for the project"}
            ]
        },
        {
            "name": "monitor_health",
            "description": "Check health status of all projects and restart if needed",
            "arguments": []
        },
        {
            "name": "view_project_logs",
            "description": "View logs for a specific project with filtering",
            "arguments": [
                {"name": "project_name", "description": "Name of the project"},
                {"name": "filter", "description": "Filter by: all, error, warn"}
            ]
        },
    ]


@server.get_prompt()
async def get_prompt(name: str, arguments: dict) -> dict:
    """Get a prompt."""
    if name == "deploy_project":
        return {
            "messages": [
                {
                    "role": "user",
                    "content": f"Deploy the project '{arguments.get('project_name')}' from {arguments.get('repo_url')} to the VPS. Use the create_project tool."
                }
            ]
        }
    elif name == "monitor_health":
        return {
            "messages": [
                {
                    "role": "user",
                    "content": "Check the health status of all projects and restart any that are dead or unhealthy."
                }
            ]
        }
    else:
        return {"messages": []}


async def main():
    """Start the MCP server."""
    async with server:
        print("devps MCP Server running on stdio", file=sys.stderr)
        await server.wait()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
