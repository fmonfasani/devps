# MCP Server Phase 1 — Implementation & Testing

## Overview

Phase 1 implements a complete MCP Server with:
- ✅ Full MCP protocol (stdio)
- ✅ Tool discovery (`list_tools`)
- ✅ Tool execution (`call_tool`)
- ✅ 2 sample tools: `devps.projects.list`, `devps.projects.get`
- ✅ RBAC integration (no duplicate auth system)
- ✅ Complete test coverage

This is a **working adapter** that proves the pattern for Phase 2.

---

## Files Added

### MCP Server Implementation

```
agent/devps_agent/mcp/
├── __init__.py              # Module marker
├── context.py               # MCPContext (auth + RBAC)
├── server.py                # MCP Server (stdio protocol)
├── schemas.py               # Pydantic models
├── client.py                # Manual test client
└── tools/
    ├── __init__.py          # Tool registry
    └── projects.py          # 2 sample tools
```

### Tests

```
tests/
├── test_mcp_server.py       # Unit tests (server, context, protocol)
└── test_mcp_integration.py  # Integration tests (full flow with RBAC)
```

### Configuration

```
agent/pyproject.toml        # Added mcp>=0.1.0,<1.0
```

---

## Architecture

### Tool Delegation Pattern

Each tool is a thin adapter:

```python
# MCP request arrives
{"method": "call_tool", "params": {"name": "devps.projects.list", "arguments": {}}}
    ↓
# Server routes to tool handler
await _list_projects(context, **arguments)
    ↓
# Tool checks RBAC using context
context.require_permission("list_projects")
    ↓
# Tool delegates to existing DEVPS capability
registry.list_projects()
    ↓
# Result serialized and returned
{"success": true, "content": "{...}"}
```

**Key principle:** Tools never duplicate logic. They delegate to existing DEVPS modules.

---

## Running the MCP Server

### Option 1: Standalone (Development)

```bash
cd agent
python -m devps_agent.mcp.server [optional_username]
```

Example (anonymous mode):
```bash
python -m devps_agent.mcp.server
```

Example (authenticated as admin):
```bash
python -m devps_agent.mcp.server "admin@example.com"
```

Server waits for stdin, accepts JSON-encoded requests, outputs JSON-encoded responses.

### Option 2: Within FastAPI (Future)

MCP can be integrated into main.py as a lifespan event:

```python
from fastapi import FastAPI
from devps_agent.mcp.server import MCPServer

app = FastAPI()

@app.on_event("startup")
async def start_mcp():
    # Start MCP server (stdio or HTTP)
    pass
```

This is Phase 3 work.

---

## Testing

### Run All Tests

```bash
cd agent
pytest tests/test_mcp_*.py -v
```

### Run Specific Tests

```bash
# Unit tests only
pytest tests/test_mcp_server.py -v

# Integration tests only
pytest tests/test_mcp_integration.py -v

# Single test
pytest tests/test_mcp_server.py::TestMCPServer::test_list_tools -v
```

### Test Coverage

**Unit Tests (`test_mcp_server.py`):**
- ✅ Server initialization (anonymous, authenticated, invalid user)
- ✅ Tool discovery (list_tools returns all tools + schemas)
- ✅ Tool execution (call_tool with valid/invalid inputs)
- ✅ RBAC checks (admin, deployer, viewer roles)
- ✅ Error handling (malformed requests, missing arguments, tool not found)

**Integration Tests (`test_mcp_integration.py`):**
- ✅ Full flow: admin lists all projects
- ✅ Full flow: deployer gets own project
- ✅ RBAC enforcement: deployer cannot access others' projects
- ✅ RBAC enforcement: viewer can list all projects (read-only)
- ✅ Tool discovery returns complete information
- ✅ Error handling: project not found

---

## Manual Testing

### Using the Client

```bash
cd agent
python -m devps_agent.mcp.client
```

This starts an MCP server and connects an interactive client that:
1. Lists available tools
2. Calls `devps.projects.list` tool
3. Displays results

### Using Your Own MCP Client

```python
import asyncio
import json
from devps_agent.mcp.client import StdioMCPClient
import subprocess
import sys

async def test():
    # Start server
    server = subprocess.Popen(
        [sys.executable, "-m", "devps_agent.mcp.server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )
    
    client = StdioMCPClient(server)
    
    # List tools
    response = await client.list_tools()
    print(json.dumps(response, indent=2))
    
    # Call tool
    response = await client.call_tool("devps.projects.list")
    print(json.dumps(response, indent=2))
    
    await client.close()

asyncio.run(test())
```

---

## Protocol Details

### Request Format

```json
{
  "method": "list_tools" | "call_tool",
  "params": {
    "name": "tool.name",           // Required for call_tool
    "arguments": {...}             // Optional, required for call_tool
  }
}
```

### Response Format

```json
{
  "success": true | false,
  "content": "json-string",        // For call_tool success
  "tools": [...],                  // For list_tools success
  "error": "error message"         // If success=false
}
```

### Example: List Tools

**Request:**
```json
{"method": "list_tools"}
```

**Response:**
```json
{
  "success": true,
  "tools": [
    {
      "name": "devps.projects.list",
      "description": "List all projects accessible to the user",
      "inputSchema": {
        "type": "object",
        "properties": {
          "filter_owner": {"type": "string"},
          "filter_status": {"type": "string"}
        }
      }
    },
    {
      "name": "devps.projects.get",
      "description": "Get detailed information about a specific project",
      "inputSchema": {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"]
      }
    }
  ]
}
```

### Example: Call Tool (Success)

**Request:**
```json
{
  "method": "call_tool",
  "params": {
    "name": "devps.projects.list",
    "arguments": {}
  }
}
```

**Response:**
```json
{
  "success": true,
  "content": "{\"projects\": [{\"name\": \"my-app\", ...}]}"
}
```

### Example: Call Tool (RBAC Error)

**Request:**
```json
{
  "method": "call_tool",
  "params": {
    "name": "devps.projects.list",
    "arguments": {}
  }
}
```

**Response (unauthenticated):**
```json
{
  "success": false,
  "error": "Authorization failed: Not authenticated"
}
```

---

## RBAC Integration

MCP uses **existing DEVPS RBAC**, not a separate auth system.

### How It Works

1. **Server initializes with username** (or None for anon):
   ```python
   server = MCPServer(authenticated_user="admin@example.com")
   ```

2. **Context loads user from registry**:
   ```python
   context = MCPContext.from_username("admin@example.com")
   # Loads: username, role, created_at from database
   ```

3. **Tools check permissions using existing rbac module**:
   ```python
   # Uses rbac.require_permission() (same as dashboard)
   context.require_permission("list_projects")
   ```

4. **Same role hierarchy as dashboard**:
   - **Admin**: Full access to all tools/projects
   - **Deployer**: Can create/manage own projects only
   - **Viewer**: Read-only access to all projects

### Permission Matrix

| Tool | Permission | Admin | Deployer | Viewer |
|------|-----------|-------|----------|--------|
| projects.list | list_projects | ✅ | ✅ (own only) | ✅ |
| projects.get | view_project | ✅ | ✅ (own only) | ✅ |

---

## Phase 1 Acceptance Criteria

✅ Server starts without errors
✅ MCP client can discover tools (`list_tools`)
✅ MCP client can call tools (`call_tool`)
✅ `devps.projects.list` returns actual projects
✅ `devps.projects.get` returns project details
✅ RBAC enforced: admin sees all, deployer sees own, viewer sees all
✅ RBAC enforced: deployer cannot access others' projects
✅ No changes to existing registry.py, docker_ops.py, rbac.py
✅ All unit tests pass
✅ All integration tests pass
✅ Monorepo stays green

---

## Phase 2 Preview

Once Phase 1 is approved, Phase 2 extends the same pattern to:
- 4 more project tools (deploy, adopt, delete, create-auto)
- 3 container tools (status, restart, logs)
- 2 health tools (status, check)
- 3 alert tools (configure, mute, unmute)
- 2 event tools (get, list)
- 2 migration tools (list, transition)
- 4 user tools (list, create, update-role, delete)

Each tool follows the same pattern:
1. Define tool function in tools/*.py
2. Register in tools/__init__.py
3. Add schema in schemas.py
4. Write tests

---

## Notes for Reviewers

### What Changed

- ✅ Added `mcp/` directory (new)
- ✅ Added tests (new)
- ✅ Modified `pyproject.toml` (added mcp dependency)
- ✅ NO changes to core DEVPS modules

### What Didn't Change

- ✅ registry.py (unchanged)
- ✅ docker_ops.py (unchanged)
- ✅ rbac.py (unchanged)
- ✅ dashboard.py (unchanged)
- ✅ No business logic moved or duplicated

### Why This Approach

1. **Adapter pattern**: MCP is protocol layer, not business logic
2. **Composition**: Tools compose existing capabilities
3. **Minimal code**: Only protocol handling is new
4. **Testability**: Tools delegated to existing, tested modules
5. **Reusability**: Phase 2 extends the same pattern

---

## Next Steps (Phase 2)

1. Merge Phase 1
2. Extend with 18 more tools (same pattern)
3. Test Phase 2 coverage
4. Approve Phase 2
5. Phase 3: HTTP transport + security

