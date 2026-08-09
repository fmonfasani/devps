# MCP Server Implementation Plan for DEVPS

## Architecture Diagram

```
External MCP Client (AgentOS)
       │
       │ HTTPS/WSS
       ▼
┌─────────────────────────┐
│  MCP Server (stdio)     │
│  + HTTP transport       │
│  (new, minimal)         │
└──────────┬──────────────┘
           │
     ┌─────▼──────┐
     │ Tooling    │ (new, minimal adapter code)
     └─────┬──────┘
           │
     ┌─────▼─────────────────────────┐
     │ DEVPS Core Capabilities       │ (existing, no changes)
     │ (reuse completely)            │
     ├─────────────────────────────┤
     │ ✅ registry.py              │
     │ ✅ docker_ops.py            │
     │ ✅ health_checks.py         │
     │ ✅ alerting.py              │
     │ ✅ github_ops.py            │
     │ ✅ rbac.py                  │
     │ ✅ dashboard.py endpoints   │
     └─────┬─────────────────────────┘
           │
     ┌─────▼──────────┬──────────┬──────────┐
     │                │          │          │
  ┌──▼───┐        ┌───▼──┐  ┌──▼──┐  ┌──▼──┐
  │Docker│        │ Git  │  │Nginx│  │SQLite
  │Daemon│        │      │  │     │  │ DB
  └──────┘        └──────┘  └─────┘  └─────┘
```

## What Changes

**New files (minimal):**
- `mcp/server.py` - MCP Server entrypoint (stdio + HTTP)
- `mcp/tools/` - Tool definitions (references existing capabilities)
- `mcp/resources/` - Resource handlers
- `mcp/auth.py` - Auth adapter (uses existing session/RBAC)
- `mcp/schemas/` - Input/output schemas

**Modified files (minimal):**
- `main.py` - Add MCP startup option
- `config.py` - MCP_ENABLED, MCP_PORT, MCP_AUTH config

**ZERO changes to:**
- registry.py
- docker_ops.py
- health_checks.py
- alerting.py
- github_ops.py
- rbac.py
- dashboard.py (its endpoints still work)

---

## MCP Tool Implementation Strategy

### Pattern: Delegation

Each MCP tool is a thin adapter that:
1. Receives input from MCP protocol
2. Validates via schema
3. Checks RBAC (if authenticated)
4. Delegates to existing DEVPS capability
5. Returns output via MCP protocol

**Never:**
- Reimplement logic
- Duplicate code
- Create new services
- Add business logic

**Example:**

```python
# ❌ WRONG
@mcp_tool("devps.projects.list")
async def list_projects(filter_owner=None):
    # Query DB directly
    with connect() as conn:
        rows = conn.execute("SELECT * FROM projects").fetchall()
    return [dict(r) for r in rows]

# ✅ CORRECT
@mcp_tool("devps.projects.list")
async def list_projects_tool(context, filter_owner=None):
    # Use existing capability
    return registry.list_projects()
```

---

## Transport Strategy

### Development (Local)

Use stdio (default MCP protocol):
```bash
python -m devps_agent.mcp.server --transport stdio
```

### Production (Remote AgentOS)

Use HTTP/SSE (Streamable HTTP):
```bash
python -m devps_agent.mcp.server --transport http --port 9500
```

MCP Server listens on:
- Endpoint: `http://VPS_IP:9500/mcp`
- Authorization: HTTPS + Bearer token (session or MCP-specific)

### Single Implementation

No code duplication:
```python
# mcp/transport.py
class Transport(ABC):
    async def handle_request(request: Tool | Resource | Prompt):
        # Common logic
        
class StdioTransport(Transport):
    # Line-based protocol
    
class HttpTransport(Transport):
    # FastAPI endpoints
```

---

## Authentication & Authorization

### How It Works

1. **Client connects** with MCP client
2. **Auth happens** at transport layer (depends on transport)
3. **Every tool call** includes authenticated context
4. **RBAC checked** before delegation to DEVPS capability
5. **Same permissions** as web dashboard

### Stdio (Local Dev)

No auth needed (same machine). Skip auth checks.

### HTTP (Remote)

- Client sends: `Authorization: Bearer <token>`
- Token: existing DEVPS session token (or new MCP-only token)
- Server validates token → gets username → enforces RBAC
- Tool execution: `context.user = registry.get_user(username)`

---

## Directory Structure

```
devps/
├── agent/
│   └── devps_agent/
│       ├── mcp/                           # NEW (minimal)
│       │   ├── __init__.py
│       │   ├── server.py                  # MCP Server + transport selection
│       │   ├── auth.py                    # Auth adapter (uses existing rbac)
│       │   ├── schemas.py                 # Pydantic input/output models
│       │   ├── tools/
│       │   │   ├── __init__.py
│       │   │   ├── projects.py            # Adapters to registry.py
│       │   │   ├── containers.py          # Adapters to docker_ops.py
│       │   │   ├── health.py              # Adapters to health_checks.py
│       │   │   ├── alerts.py              # Adapters to alerting.py
│       │   │   ├── events.py              # Adapters to registry.py
│       │   │   ├── migrations.py          # Adapters to registry.py
│       │   │   └── users.py               # Adapters to registry.py
│       │   ├── resources/
│       │   │   ├── __init__.py
│       │   │   ├── projects.py            # Read-only project snapshots
│       │   │   ├── health.py              # Read-only health snapshots
│       │   │   └── migrations.py
│       │   └── transport/
│       │       ├── __init__.py
│       │       ├── base.py                # Transport abstraction
│       │       ├── stdio.py               # Line-based MCP protocol
│       │       └── http.py                # HTTP/SSE transport
│       │
│       ├── registry.py                     # ← NO CHANGES
│       ├── docker_ops.py                  # ← NO CHANGES
│       ├── health_checks.py               # ← NO CHANGES
│       ├── alerting.py                    # ← NO CHANGES
│       ├── github_ops.py                  # ← NO CHANGES
│       ├── rbac.py                        # ← NO CHANGES
│       ├── dashboard.py                   # ← NO CHANGES
│       ├── auth.py                        # ← NO CHANGES
│       ├── main.py                        # ← MINOR: add MCP startup
│       └── config.py                      # ← MINOR: add MCP config
│
└── MCP_IMPLEMENTATION_PLAN.md             # This file
└── CAPABILITY_INVENTORY.md                # Tool definitions
```

---

## Phase Implementation

### Phase 1: Minimal Server (Ready for approval)

**Goal:** Prove architecture + verify existing capabilities work

**Deliverables:**
1. `mcp/server.py` - Basic MCP server (stdio only for now)
2. `mcp/tools/projects.py` - Implement 2 tools:
   - `devps.projects.list`
   - `devps.projects.get`
3. `mcp/auth.py` - Pass-through auth (skip for stdio)
4. Test: Manual MCP client connects → calls tools → gets results

**Acceptance Criteria:**
- ✅ Server starts without errors
- ✅ MCP client can discover tools
- ✅ `devps.projects.list` returns actual projects
- ✅ `devps.projects.get` returns project details
- ✅ No changes to existing registry.py or other core files
- ✅ All tests pass

### Phase 2: Core Tools (Complete coverage)

Implement all 22 tools:
- Projects (6)
- Containers (3)
- Health (2)
- Alerts (3)
- Events (2)
- Migrations (2)
- Users (4)

### Phase 3: HTTP Transport + Security

- Implement HTTP/SSE transport
- Session auth (Bearer token)
- RBAC enforcement on tool calls
- Rate limiting
- Logging/observability

### Phase 4: Resources & Prompts (Optional)

- Implement read-only resources
- MCP prompts for common workflows
- Example: `agentos://projects` resource

---

## Dependencies & Versions

### Current DEVPS Stack

```
FastAPI        4.21.0
Pydantic       2.x (from FastAPI)
SQLite3        (stdlib)
Docker CLI     (subprocess wrapper, no SDK)
Nginx CLI      (subprocess wrapper)
Git CLI        (subprocess wrapper)
```

### MCP SDK Required

```
@modelcontextprotocol/sdk  1.x (latest stable)
```

**Why no separate MCP dependency?** Most MCP operations are protocol-level (JSON, stdio). The Python MCP SDK is lightweight.

### No Additional Dependencies

- No ORM changes (SQLite raw queries stay)
- No async/await changes (FastAPI already async)
- No new frameworks or middleware

---

## Testing Strategy

### Unit Tests (tools/*)

Test each tool adapter:
```python
def test_devps_projects_list():
    # Mock registry.list_projects()
    # Call tool
    # Assert output matches schema
```

### Integration Tests (server + real DB)

```python
def test_mcp_server_discover_tools():
    # Start MCP server
    # Connect MCP client
    # List tools
    # Assert 22 tools present

def test_mcp_tool_list_projects():
    # Create test project in real DB
    # Call tool via MCP
    # Assert response
```

### E2E Tests (server + DB + docker)

(Optional, only if tools make docker calls)

---

## Implementation Checklist

**Before starting Phase 1:**

- [ ] Approve CAPABILITY_INVENTORY.md (22 tools, input/output schemas)
- [ ] Approve directory structure
- [ ] Confirm MCP SDK version to use
- [ ] Confirm stdio-only for Phase 1 (HTTP later)
- [ ] Confirm: no changes to registry.py, docker_ops.py, etc.

**During Phase 1:**

- [ ] Create mcp/ directory structure
- [ ] Implement MCP server entrypoint
- [ ] Implement 2 sample tools (projects.list, projects.get)
- [ ] Write unit tests
- [ ] Verify no existing functionality broken

**Before Phase 2:**

- [ ] Approve Phase 1 implementation
- [ ] Review code for reusability patterns
- [ ] Plan Phase 2 timeline

---

## Success Criteria

When complete, this MCP Server enables:

1. **AgentOS connects** to DEVPS MCP Server via HTTPS
2. **AgentOS discovers** 22 tools + resources
3. **AgentOS calls** tools (e.g., `devps.projects.list`)
4. **DEVPS executes** via existing capabilities (registry, docker_ops, etc)
5. **Results returned** to AgentOS via MCP protocol
6. **RBAC enforced** (only authorized users/roles can call tools)
7. **No duplication** of logic
8. **Monorepo stays green** (all tests pass)

---

## Notes for Developers

### Principles

1. **Adapter, not domain** - MCP server is adapter, not business logic
2. **Composition, not inheritance** - tools compose existing capabilities
3. **Minimal new code** - write only what's necessary for MCP protocol
4. **Existing tests unchanged** - don't refactor core modules
5. **Security first** - auth/RBAC always checked before action

### Common Mistakes to Avoid

- ❌ Duplicating registry queries in tool code
- ❌ Refactoring docker_ops.py to add MCP-specific methods
- ❌ Creating new ExecutionContext or capability types
- ❌ Hardcoding tool logic instead of delegating
- ❌ Skipping RBAC checks for "simplicity"
- ❌ Adding new config to existing files without review

### Code Style

Use same patterns as existing DEVPS:
- Type hints throughout
- Docstrings on public functions
- Exceptions for errors (not return codes)
- Logging for observability
- Minimal comments (code is self-documenting)

