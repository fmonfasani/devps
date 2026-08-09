# MCP Server for AgentOS/devps

## Overview

AgentOS exposes all its operational capabilities through the **Model Context Protocol (MCP)**, enabling:

1. **External Integration**: Any MCP client (Claude Code, OpenCode, custom tools) can discover and use AgentOS capabilities
2. **Self-Consumption**: AgentOS can consume its own MCP Server as a client
3. **Standardized Interface**: All capabilities follow MCP standards for tools, resources, and prompts

```
                    ┌──────────────────────┐
                    │      AgentOS Core    │
                    │                      │
                    │ Projects             │
                    │ Health Monitoring    │
                    │ Users                │
                    │ Deployments          │
                    │ Alerts               │
                    └──────────┬───────────┘
                               │
                         MCP Server
                               │
              ┌────────────────┼────────────────┐
              │                │                │
          MCP Client       MCP Client       MCP Client
          (AgentOS)       (Claude Code)    (Custom)
```

---

## Installation

```bash
pip install mcp
```

## Starting the MCP Server

### Option 1: Standalone
```bash
python -m devps_agent.mcp_server
```

### Option 2: Within AgentOS
```python
from devps_agent.mcp_server import server, main
import asyncio

asyncio.run(main())
```

### Option 3: Configure in MCP Client
```json
{
  "mcp_servers": {
    "devps": {
      "command": "python",
      "args": ["-m", "devps_agent.mcp_server"]
    }
  }
}
```

---

## Tools

### Project Management

#### `list_projects`
List all projects with their status.

**Arguments:**
- `owner` (string, optional): Filter by project owner

**Example:**
```python
client.call_tool("list_projects", {"owner": "admin"})
```

**Response:**
```json
[
  {
    "name": "my-app",
    "status": "deployed",
    "health_status": "running",
    "domain": "my-app.com",
    "owner": "admin"
  }
]
```

---

#### `get_project`
Get detailed information about a specific project.

**Arguments:**
- `project_name` (string, required): Project name

**Example:**
```python
client.call_tool("get_project", {"project_name": "my-app"})
```

**Response:**
```json
{
  "name": "my-app",
  "status": "deployed",
  "health_status": "running",
  "restart_count": 2,
  "domain": "my-app.com",
  "ports": [{"service": "app", "host_port": 3000, "container_port": 3000}],
  "last_health_check_at": "2026-08-09T12:30:45Z",
  "last_restart_at": "2026-08-09T11:00:00Z"
}
```

---

#### `create_project`
Create a new project (auto-generates GitHub repo + deploys).

**Arguments:**
- `project_name` (string, required): Project name
- `domain` (string, optional): Domain for the project

**Example:**
```python
client.call_tool("create_project", {
  "project_name": "new-app",
  "domain": "new-app.example.com"
})
```

**Response:**
```json
{
  "project_name": "new-app",
  "repo_url": "https://github.com/user/new-app.git",
  "port": 40002,
  "message": "Project created and deploying..."
}
```

---

#### `restart_project`
Restart a running project's container.

**Arguments:**
- `project_name` (string, required): Project name

**Example:**
```python
client.call_tool("restart_project", {"project_name": "my-app"})
```

---

#### `stop_project`
Stop a running project.

**Arguments:**
- `project_name` (string, required): Project name

---

### Logs & Debugging

#### `get_logs`
Get container logs for a project.

**Arguments:**
- `project_name` (string, required): Project name
- `tail` (integer, optional): Number of lines (default: 100)
- `filter` (string, optional): Filter by level (all/error/warn, default: all)

**Example:**
```python
# Get last 200 lines
client.call_tool("get_logs", {
  "project_name": "my-app",
  "tail": 200
})

# Get only errors
client.call_tool("get_logs", {
  "project_name": "my-app",
  "filter": "error"
})
```

---

#### `get_events`
Get recent events for a project.

**Arguments:**
- `project_name` (string, required): Project name
- `limit` (integer, optional): Number of events (default: 10)

**Example:**
```python
client.call_tool("get_events", {
  "project_name": "my-app",
  "limit": 20
})
```

---

### Health Monitoring

#### `get_health_status`
Get health status of all projects.

**Example:**
```python
client.call_tool("get_health_status", {})
```

**Response:**
```json
[
  {
    "name": "my-app",
    "status": "running",
    "restart_count": 2,
    "last_check": "2026-08-09T12:30:45Z"
  },
  {
    "name": "other-app",
    "status": "dead",
    "restart_count": 5,
    "last_check": "2026-08-09T12:30:44Z"
  }
]
```

---

#### `get_project_health`
Get detailed health information for a specific project.

**Arguments:**
- `project_name` (string, required): Project name

---

### Alerts

#### `configure_alerts`
Configure alerts for a project.

**Arguments:**
- `project_name` (string, required)
- `email` (string, optional): Alert email
- `slack` (string, optional): Slack webhook URL
- `enabled` (boolean, required): Enable/disable alerts

**Example:**
```python
client.call_tool("configure_alerts", {
  "project_name": "my-app",
  "email": "ops@example.com",
  "slack": "https://hooks.slack.com/...",
  "enabled": True
})
```

---

#### `mute_alerts`
Mute alerts for a project temporarily.

**Arguments:**
- `project_name` (string, required)
- `hours` (integer, required): Hours to mute (1-24)

**Example:**
```python
# Mute for 4 hours during maintenance
client.call_tool("mute_alerts", {
  "project_name": "my-app",
  "hours": 4
})
```

---

### User Management

#### `list_users`
List all users.

**Example:**
```python
client.call_tool("list_users", {})
```

**Response:**
```json
[
  {"username": "admin@example.com", "role": "admin", "created_at": "2026-08-01T10:00:00Z"},
  {"username": "dev@example.com", "role": "deployer", "created_at": "2026-08-05T15:30:00Z"}
]
```

---

#### `create_user`
Create a new user.

**Arguments:**
- `username` (string, required): Email/username
- `password` (string, required): User password
- `role` (string, required): admin/deployer/viewer

---

#### `update_user_role`
Update a user's role.

**Arguments:**
- `username` (string, required)
- `role` (string, required): admin/deployer/viewer

---

### Deployments & Migrations

#### `deploy_project`
Deploy a project from GitHub.

**Arguments:**
- `project_name` (string, required)
- `repo_url` (string, required): GitHub URL
- `git_ref` (string, optional): Branch/tag (default: main)
- `domain` (string, optional): Domain

---

#### `get_migrations`
List ongoing project migrations.

**Example:**
```python
client.call_tool("get_migrations", {})
```

---

## Resources

Resources expose AgentOS state as queryable documents. Use the URI scheme `devps://` to access them.

### Available Resources

| URI | Description |
|-----|-------------|
| `devps://projects` | List all projects |
| `devps://project/{project_name}` | Project details |
| `devps://project/{project_name}/logs` | Live logs |
| `devps://health` | Health status |

### Examples

```python
# Get all projects
projects = await client.read_resource("devps://projects")

# Get specific project
project = await client.read_resource("devps://project/my-app")

# Get live logs
logs = await client.read_resource("devps://project/my-app/logs")

# Get health status
health = await client.read_resource("devps://health")
```

---

## Prompts

Common operation prompts guide agents through typical workflows.

### Available Prompts

| Name | Description |
|------|-------------|
| `deploy_project` | Deploy new project from GitHub |
| `monitor_health` | Check health and auto-restart |
| `view_project_logs` | View and filter logs |

### Example

```python
prompt = await client.get_prompt("deploy_project", {
  "project_name": "new-app",
  "repo_url": "https://github.com/user/new-app"
})
```

---

## Using MCP Client in AgentOS

### Python Example

```python
from devps_agent.mcp_client import DevpsMCPClient
import asyncio

async def monitor_and_restart():
    """Monitor health and restart dead projects."""
    async with DevpsMCPClient() as client:
        # Get health status
        health = await client.get_health_status()

        # Restart any dead projects
        for project in health:
            if project["status"] == "dead":
                print(f"Restarting {project['name']}...")
                await client.restart_project(project["name"])

        # Mute alerts during maintenance
        await client.mute_alerts("my-app", hours=2)

        # Get logs for debugging
        logs = await client.get_logs("my-app", filter_type="error")
        print(logs)

asyncio.run(monitor_and_restart())
```

---

## Integration with Other MCP Clients

### Claude Code
Configure in `.claudecode/mcp.json`:
```json
{
  "mcp_servers": {
    "devps-agent": {
      "command": "python",
      "args": ["-m", "devps_agent.mcp_server"],
      "disabled": false
    }
  }
}
```

Then use in prompts:
> "List all projects and show me the logs for any that are currently unhealthy"

---

### Custom MCP Client
```python
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client

async def main():
    async with ClientSession(stdio_client(["python", "-m", "devps_agent.mcp_server"])) as session:
        # List tools
        tools = await session.list_tools()
        print(tools)

        # Call tool
        result = await session.call_tool("list_projects", {})
        print(result)

        # Read resource
        projects = await session.read_resource("devps://projects")
        print(projects)
```

---

## Error Handling

Tools return structured results:

```python
result = await client.call_tool("list_projects", {})
# result = {
#   "success": bool,
#   "content": str,
#   "error": str | None
# }

if result["success"]:
    projects = json.loads(result["content"])
else:
    print(f"Error: {result['error']}")
```

---

## Best Practices

1. **Always use context manager**: Ensures proper connection handling
   ```python
   async with DevpsMCPClient() as client:
       # ...
   ```

2. **Cache tool list**: Don't call `list_tools()` repeatedly
   ```python
   async with DevpsMCPClient() as client:
       tools = await client.list_tools()
       # Reuse tools for multiple calls
   ```

3. **Use specific filter for logs**: Avoid fetching massive log streams
   ```python
   # Good: Filter by error level
   logs = await client.get_logs("my-app", filter_type="error")

   # Avoid: Get all logs
   logs = await client.get_logs("my-app")
   ```

4. **Batch operations**: Reuse single connection for multiple calls
   ```python
   async with DevpsMCPClient() as client:
       for project in projects:
           health = await client.get_project_health(project)
           # ...
   ```

5. **Monitor health regularly**: Schedule health checks
   ```python
   import asyncio
   
   async def health_monitor():
       async with DevpsMCPClient() as client:
           while True:
               health = await client.get_health_status()
               # Process and alert
               await asyncio.sleep(60)
   ```

---

## API Stability

The MCP Server API is versioned alongside AgentOS. Breaking changes are announced 2 weeks in advance.

- **Current version**: 1.0.0
- **Supported versions**: 1.x.x
- **Deprecated features**: None

---

## Support

- **Issues**: Create an issue in the devps repository
- **Discussions**: Use GitHub Discussions
- **Documentation**: See `MCP_SERVER.md` (this file)

