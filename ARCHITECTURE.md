# AgentOS/devps - Complete Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER INTERFACES                         │
├──────────────────────┬──────────────────────┬──────────────────┤
│   Web Dashboard      │   MCP Clients        │   Direct API     │
│  (browser/mobile)    │  (Claude Code, etc)  │   (REST/gRPC)    │
└──────────┬───────────┴──────────┬───────────┴────────┬──────────┘
           │                      │                    │
           └──────────────────────┼────────────────────┘
                                  │
                    ┌─────────────▼──────────────┐
                    │   FastAPI Agent (9400)     │
                    │                            │
                    │  ┌────────────────────┐   │
                    │  │  MCP Server        │   │
                    │  │  (Tools/Resources) │   │
                    │  └────────────────────┘   │
                    │                            │
                    │  ┌────────────────────┐   │
                    │  │  Dashboard Routes  │   │
                    │  │  (login, projects) │   │
                    │  └────────────────────┘   │
                    │                            │
                    │  ┌────────────────────┐   │
                    │  │  RBAC System       │   │
                    │  │  (3 roles)         │   │
                    │  └────────────────────┘   │
                    │                            │
                    │  ┌────────────────────┐   │
                    │  │  Health Monitor    │   │
                    │  │  (async loop)      │   │
                    │  └────────────────────┘   │
                    └─────────────┬──────────────┘
                                  │
                  ┌───────────────┼───────────────┐
                  │               │               │
        ┌─────────▼────────┐  ┌───▼─────────┐  ┌─▼────────────┐
        │   SQLite DB      │  │   Docker    │  │   GitHub     │
        │                  │  │   Daemon    │  │   API        │
        │ • users          │  │             │  │              │
        │ • projects       │  │ • containers│  │ • repos      │
        │ • events         │  │ • logs      │  │ • webhooks   │
        │ • migrations     │  │ • health    │  │ • ci/cd      │
        │ • alerts         │  │ • ports     │  │              │
        └──────────────────┘  └─────────────┘  └──────────────┘
```

---

## Component Breakdown

### 1. FastAPI Agent (Core)
**Location**: `agent/devps_agent/`

```
agent/
├── main.py                  # FastAPI app + lifespan setup
├── dashboard.py             # Web UI routes
├── auth.py                  # Login + password hashing
├── rbac.py                  # Role-based access control
├── registry.py              # SQLite wrapper (projects/users/events)
├── health_checks.py         # Health monitoring loop
├── docker_ops.py            # Docker compose management
├── config.py                # Configuration from env
├── models.py                # Request/response models
│
├── routers/
│   ├── projects.py          # Project API (POST /projects/deploy)
│   ├── health_status.py     # Health API (GET /health/status)
│   └── webhooks.py          # GitHub webhooks
│
├── mcp_server.py            # MCP Server (NEW)
├── mcp_client.py            # MCP Client (NEW)
│
└── templates/
    ├── login.html
    ├── projects.html
    ├── project_detail.html  # View logs, restart, etc
    ├── health_status.html   # Real-time monitoring
    ├── users.html           # Admin management
    └── migrations.html
```

### 2. MCP Server
**File**: `agent/devps_agent/mcp_server.py`

Exposes AgentOS capabilities to external MCP clients:

**Tools** (22 total):
- Project: list, get, create, restart, stop
- Logs: get_logs, get_events, with filtering
- Health: get_health_status, get_project_health
- Alerts: configure_alerts, mute_alerts
- Users: list, create, update_role
- Deployments: deploy_project, get_migrations

**Resources** (URI-based):
- `devps://projects` - All projects
- `devps://project/{name}` - Project details
- `devps://project/{name}/logs` - Live logs
- `devps://health` - Health status

**Prompts** (Common workflows):
- deploy_project - Deploy from GitHub
- monitor_health - Auto-restart unhealthy
- view_project_logs - View with filtering

### 3. MCP Client
**File**: `agent/devps_agent/mcp_client.py`

Allows AgentOS to consume its own MCP Server:

```python
async with DevpsMCPClient() as client:
    # List projects
    projects = await client.list_projects()
    
    # Get health
    health = await client.get_health_status()
    
    # Restart dead projects
    for h in health:
        if h["status"] == "dead":
            await client.restart_project(h["name"])
    
    # Get logs
    logs = await client.get_logs("my-app", filter_type="error")
    
    # Configure alerts
    await client.configure_alerts("my-app", 
        email="ops@example.com", enabled=True)
```

### 4. Database Schema
**File**: `agent/devps_agent/db.py`

```sql
-- Users (RBAC)
users (
  username (PK),
  password_hash,
  password_salt,
  role (admin/deployer/viewer),
  created_at
)

-- Projects
projects (
  name (PK),
  managed_by (devps/adopted),
  repo_url,
  git_ref,
  domain,
  status,
  health_status,
  restart_count,
  owner (FK user),
  alert_email,
  alert_slack,
  alert_enabled,
  alert_muted_until
)

-- Port Mapping
project_ports (
  project_name (FK),
  service,
  host_port (U),
  container_port
)

-- Event Log (append-only)
events (
  id (PK),
  project_name (FK),
  kind,
  detail,
  success,
  created_at,
  created_by (FK user)
)

-- Migrations
migrations (
  project_name (PK, FK),
  source_description,
  adopted_at,
  paralleled_at,
  cutover_at,
  decommissioned_at
)
```

### 5. Key Features

#### Authentication & Authorization
```
Login (email/password)
  ↓
PBKDF2-SHA256 verification
  ↓
Session token (signed cookie)
  ↓
RBAC check for each endpoint
  ├── admin: full access
  ├── deployer: own projects + create
  └── viewer: read-only
```

#### Health Monitoring Loop
```
Every 30 seconds:
  1. Get all projects
  2. Check container status
  3. On failure:
     - Increment restart_count
     - Try restart (max 5/hour)
     - Exponential backoff
     - Create event
     - Send alerts (email/Slack)
  4. Update last_health_check_at
```

#### Project Creation (Auto)
```
User enters: "my-app"
  ↓
Validate name
  ↓
GitHub API: Create repo
  ↓
Clone repo locally
  ↓
Generate files:
  - docker-compose.yml
  - Dockerfile
  - package.json
  - index.js
  ↓
Git: add, commit, push
  ↓
Docker: build + run
  ↓
Assign port (40000-40999)
  ↓
Register in DB
  ↓
Start health monitoring
  ↓
Dashboard shows as "deployed" (30 sec later)
```

---

## Data Flow Diagram

### Login Flow
```
1. User: POST /dashboard/login
2. Dashboard: Verify password (PBKDF2)
3. Session: Create signed cookie
4. Redirect: /dashboard (authenticated)
```

### Create Project Flow
```
1. User: POST /dashboard/api/create-project-auto
2. Validate: Name, permissions
3. GitHub API: Create repo
4. Clone: git clone
5. Generate: Files (docker-compose, Dockerfile, etc)
6. Commit: git push
7. Docker: docker compose build + up
8. Register: INSERT into projects table
9. Monitor: Start health checks
10. Response: Project + port
```

### Health Check Flow
```
Every 30 seconds (async loop):
  1. SELECT * FROM projects
  2. For each project:
     a. docker inspect {name}
     b. Get container state
     c. Compare to DB (health_status)
     d. On change → INSERT event
     e. If dead & restart_count < 5/hour:
        i. docker compose restart
        ii. UPDATE restart_count
        iii. Send alert (email/Slack)
        iv. Exponential backoff
  3. UPDATE last_health_check_at
```

### MCP Request Flow
```
MCP Client: call_tool("list_projects")
  ↓
MCP Server: Receive via stdio
  ↓
MCP Server: Execute handler
  ↓
Handler: Call registry.list_projects()
  ↓
Registry: Query SQLite DB
  ↓
Return: JSON list of projects
  ↓
MCP Server: Return via stdout
  ↓
MCP Client: Parse + Use result
```

---

## Security Layers

### 1. Authentication
- ✅ Session-based (signed cookie)
- ✅ Password: PBKDF2-SHA256 (100k iterations)
- ✅ Rate limiting: 5 login attempts per IP

### 2. Authorization (RBAC)
- ✅ 3 roles: admin, deployer, viewer
- ✅ Per-endpoint permission checks
- ✅ Projects: owner-only (except admin)
- ✅ Users: admin-only

### 3. Data Protection
- ✅ Password salting
- ✅ No plaintext secrets in logs
- ✅ GitHub token in env (not in code)
- ✅ Foreign key constraints

### 4. API Security
- ✅ CORS disabled (VPS-only)
- ✅ Session timeout
- ✅ HTTPS required (nginx)
- ✅ SSL certificates (certbot)

---

## Deployment Architecture

```
┌─────────────────────────────────┐
│   VPS (Ubuntu 24.04)            │
├─────────────────────────────────┤
│                                 │
│  ┌───────────────────────────┐  │
│  │  Nginx (Port 80/443)      │  │
│  │  • SSL/TLS                │  │
│  │  • Reverse proxy          │  │
│  │  • Load balancer          │  │
│  └───────────┬───────────────┘  │
│              │                   │
│  ┌───────────▼───────────────┐  │
│  │  FastAPI (Port 9400)      │  │
│  │  • MCP Server             │  │
│  │  • Dashboard              │  │
│  │  • REST API               │  │
│  └───────────┬───────────────┘  │
│              │                   │
│  ┌───────────┼───────────────┐  │
│  │           │               │   │
│  │     ┌─────▼────────┐     │   │
│  │     │  SQLite DB   │     │   │
│  │     │  (/opt/data) │     │   │
│  │     └──────────────┘     │   │
│  │                          │   │
│  │     ┌──────────────┐     │   │
│  │     │  Docker      │     │   │
│  │     │  Daemon      │     │   │
│  │     │  Containers  │     │   │
│  │     └──────────────┘     │   │
│  │                          │   │
│  │     ┌──────────────┐     │   │
│  │     │  Systemd    │     │   │
│  │     │  Service    │     │   │
│  │     └──────────────┘     │   │
│  │                          │   │
│  └──────────────────────────┘  │
│                                 │
└─────────────────────────────────┘
```

---

## Performance Considerations

### Health Check Loop
- **Interval**: 30 seconds (configurable)
- **Timeout**: 10 seconds per container
- **Async**: Non-blocking I/O
- **Backoff**: 30s → 2min → 30min

### Database
- **Type**: SQLite (no separate DB server)
- **Location**: `/opt/devps/data/registry.db`
- **Indexes**: On (project_name, owner, created_at)
- **Queries**: Average <100ms

### Docker Operations
- **Build cache**: Reused between builds
- **Port range**: 40000-40999 (1000 projects max)
- **Network**: Docker bridge (isolated)

### Resource Limits
- **Memory**: ~100MB (FastAPI + health loop)
- **CPU**: <5% idle
- **Disk**: ~1GB per project (Docker images)

---

## Integration Points

### External Services
- **GitHub**: OAuth (optional), API for repo creation
- **Docker Registry**: Docker Hub (default)
- **Email**: SMTP for alerts (optional)
- **Slack**: Webhooks for alerts (optional)

### Client Integrations
- **Claude Code**: MCP server auto-discovery
- **OpenCode**: Future support planned
- **Custom Tools**: Any tool with MCP support
- **AgentOS Self**: DevpsMCPClient

---

## Monitoring & Debugging

### Logs
- **FastAPI**: Stdout (uvicorn)
- **Health**: Events table (projects.events)
- **Docker**: `docker logs {container}`
- **System**: Systemd journal

### Metrics
- **Health check runs**: events table (kind="auto_restart")
- **Project uptime**: Calculate from restart_count
- **Deployment success**: events table (success=1)
- **User activity**: events table (created_by)

### Debugging Commands
```bash
# Check service status
systemctl status devps-agent

# View logs
journalctl -u devps-agent -f

# Inspect database
sqlite3 /opt/devps/data/registry.db "SELECT * FROM projects;"

# Check health
curl http://127.0.0.1:9400/health

# Docker diagnostics
docker compose ls
docker stats
docker logs <project-name>
```

---

## Development Workflow

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run FastAPI server
python -m uvicorn devps_agent.main:app --reload --port 9400

# In another terminal, run MCP server
python -m devps_agent.mcp_server

# Run MCP client example
python -m devps_agent.mcp_client
```

### Testing
```bash
# Run unit tests
pytest tests/

# Run integration tests
pytest tests/integration/

# Run MCP client tests
pytest tests/mcp/
```

### Deployment
```bash
# Push to GitHub
git push origin main

# Trigger GitHub Actions (bootstrap.yml)
# This SSH's into VPS and:
#   1. git pull origin main
#   2. pip install -e agent/
#   3. systemctl restart devps-agent
```

---

## Future Enhancements

- [ ] Webhooks (deploy on git push)
- [ ] API keys (programmatic access)
- [ ] Rollback (version history)
- [ ] Custom domains (DNS automation)
- [ ] Environment variable UI
- [ ] Database backups
- [ ] Multi-node deployment
- [ ] Kubernetes support
- [ ] Metrics dashboard (Prometheus/Grafana)
- [ ] Log aggregation (ELK stack)

