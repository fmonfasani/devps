# DEVPS Capability Inventory & MCP Mapping

## Overview

Este documento mapea cada capacidad **existente y funcionando** en DEVPS a su correspondiente herramienta MCP. No inventamos nuevas capacidades; exponemos lo que ya existe.

Estructura: 
```
DEVPS Capability (implementación)
    ↓
Source File(s)
    ↓
MCP Tool Name
    ↓
Input Schema
    ↓
Output Schema
    ↓
RBAC Permission
    ↓
Side Effects
```

---

## 1. PROJECTS

### 1.1 List Projects

**DEVPS Implementation:**
- File: `registry.py::list_projects()`
- Endpoint: `GET /projects`
- Description: Retorna lista de todos los proyectos con puertos, eventos, etc.

**MCP Tool:**
```
devps.projects.list
```

**Input Schema:**
```json
{
  "filter_owner": "string (optional)",
  "filter_status": "string (optional: deployed, build_failed, adopting, etc)"
}
```

**Output Schema:**
```json
{
  "projects": [
    {
      "name": "string",
      "managed_by": "devps|adopted",
      "repo_url": "string",
      "git_ref": "string",
      "git_sha": "string",
      "domain": "string",
      "status": "deployed|deploying|build_failed|unknown",
      "health_status": "running|dead|unhealthy|unknown",
      "restart_count": "integer",
      "owner": "string",
      "created_at": "ISO8601",
      "updated_at": "ISO8601",
      "ports": [
        {
          "service": "string",
          "host_port": "integer",
          "container_port": "integer"
        }
      ],
      "last_event": {
        "kind": "string",
        "success": "boolean",
        "created_at": "ISO8601"
      }
    }
  ]
}
```

**RBAC:**
- Required Permission: `list_projects` (viewer+)
- Admin: Sees all projects
- Deployer: Sees only own projects
- Viewer: Sees all projects (read-only)

**Side Effects:**
- None (read-only)

---

### 1.2 Get Project Details

**DEVPS Implementation:**
- File: `registry.py::get_project(name)`
- Endpoint: `GET /projects/{name}`
- Description: Retorna detalles completos de un proyecto

**MCP Tool:**
```
devps.projects.get
```

**Input Schema:**
```json
{
  "name": "string (required)"
}
```

**Output Schema:**
```json
{
  "name": "string",
  "managed_by": "devps|adopted",
  "repo_url": "string",
  "git_ref": "string",
  "git_sha": "string",
  "domain": "string",
  "status": "string",
  "health_status": "string",
  "restart_count": "integer",
  "owner": "string",
  "created_at": "ISO8601",
  "updated_at": "ISO8601",
  "ports": [...],
  "last_event": {...}
}
```

**RBAC:**
- Required Permission: `view_project` (viewer+)
- Must be admin OR owner (if deployer)

**Side Effects:**
- None (read-only)

---

### 1.3 Deploy Project

**DEVPS Implementation:**
- File: `routers/projects.py::deploy()`
- Endpoint: `POST /projects/{name}/deploy`
- Process:
  1. Git clone/fetch/checkout (docker_ops.py)
  2. Port allocation (ports.py)
  3. Docker compose up --build (docker_ops.py)
  4. Nginx vhost installation (nginx.py)
  5. Event logging + migration tracking

**MCP Tool:**
```
devps.projects.deploy
```

**Input Schema:**
```json
{
  "name": "string (required)",
  "repo_url": "string (required)",
  "git_ref": "string (default: main)",
  "domain": "string (optional)",
  "compose_file": "string (default: docker-compose.yml)",
  "services": {
    "service_name": "container_port (integer)"
  },
  "env_file": "string (optional)",
  "primary_service": "string (required if domain set)"
}
```

**Output Schema:**
```json
{
  "name": "string",
  "status": "deployed|deploying|build_failed",
  "git_sha": "string",
  "ports": {...},
  "domain": "string"
}
```

**RBAC:**
- Required Permission: `deploy_project` (deployer+)
- Deployer can only deploy own projects (unless admin)

**Side Effects:**
- ✅ Creates/updates project in DB
- ✅ Clones/updates git repo
- ✅ Builds Docker image
- ✅ Starts container
- ✅ Allocates ports
- ✅ Creates nginx vhost (if domain set)
- ✅ Logs events
- ✅ Updates migration tracking

**Error Handling:**
- Git error → HTTP 502 + event log
- Docker build error → HTTP 502 + event log
- Nginx error → HTTP 502 (deployed, vhost failed) + event log

---

### 1.4 Adopt Project

**DEVPS Implementation:**
- File: `routers/projects.py::adopt()`
- Endpoint: `POST /projects/{name}/adopt`
- Process:
  1. Inspect existing Docker container (docker_ops.py)
  2. Register project in DB with minimal info
  3. Mark as "adopting" status
  4. Track in migrations table

**MCP Tool:**
```
devps.projects.adopt
```

**Input Schema:**
```json
{
  "name": "string (required)",
  "container_name": "string (required)",
  "description": "string (optional)"
}
```

**Output Schema:**
```json
{
  "name": "string",
  "status": "adopting",
  "health_status": "string",
  "managed_by": "adopted"
}
```

**RBAC:**
- Required Permission: `adopt_project` (admin only)

**Side Effects:**
- ✅ Registers project in DB
- ✅ Records container ports
- ✅ Creates migration record
- ✅ Logs adoption event

---

### 1.5 Delete Project

**DEVPS Implementation:**
- File: `registry.py::delete_project(name)`
- Implementation: Direct DELETE from projects table

**MCP Tool:**
```
devps.projects.delete
```

**Input Schema:**
```json
{
  "name": "string (required)"
}
```

**Output Schema:**
```json
{
  "success": "boolean"
}
```

**RBAC:**
- Required Permission: `delete_project` (admin only)

**Side Effects:**
- ✅ Removes project from DB
- ✅ Cascades to events, ports, migrations (FK constraints)
- ⚠️ Does NOT stop/remove Docker container

---

## 2. CONTAINERS

### 2.1 Get Container Status

**DEVPS Implementation:**
- File: `docker_ops.py::container_health(container_name)`
- Implementation: docker inspect + state parsing
- Returns: "running", "stopped", "unhealthy", "missing"

**MCP Tool:**
```
devps.containers.status
```

**Input Schema:**
```json
{
  "project_name": "string (required)"
}
```

**Output Schema:**
```json
{
  "project_name": "string",
  "status": "running|stopped|unhealthy|missing",
  "health": "string"
}
```

**RBAC:**
- Required Permission: `view_health` (viewer+)

**Side Effects:**
- None (read-only, docker inspect only)

---

### 2.2 Restart Container

**DEVPS Implementation:**
- File: `dashboard.py::restart_container_endpoint()` + `docker_ops.py::compose_restart()`
- Implementation: `docker compose restart`
- Restrictions: 
  - Only for `managed_by == "devps"` projects
  - No rate limiting on manual restarts
  - Logs event with username

**MCP Tool:**
```
devps.containers.restart
```

**Input Schema:**
```json
{
  "project_name": "string (required)"
}
```

**Output Schema:**
```json
{
  "success": "boolean",
  "message": "string"
}
```

**RBAC:**
- Required Permission: `edit_project` (deployer+)
- Deployer can only restart own projects (unless admin)

**Side Effects:**
- ✅ Restarts Docker container (via docker compose restart)
- ✅ Logs manual_restart event
- ✅ Does NOT increment auto-restart counter

---

### 2.3 Get Container Logs

**DEVPS Implementation:**
- File: `dashboard.py::get_logs_endpoint()` + `docker_ops.py::container_logs()`
- Implementation: `docker logs --tail N`
- Configurable tail: 10-1000 lines (default 200)

**MCP Tool:**
```
devps.containers.logs
```

**Input Schema:**
```json
{
  "project_name": "string (required)",
  "tail": "integer (default: 200, min: 10, max: 1000)"
}
```

**Output Schema:**
```json
{
  "project_name": "string",
  "logs": "string (multiline)"
}
```

**RBAC:**
- Required Permission: `view_project` (viewer+)

**Side Effects:**
- None (read-only, docker logs only)

**Limitations:**
- No log streaming (one-shot tail)
- No filtering (returns all logs, merged stdout+stderr)
- No timestamps separation

---

## 3. HEALTH & MONITORING

### 3.1 Get Health Status (All Projects)

**DEVPS Implementation:**
- File: `routers/health_status.py::list_health()`
- Source: Combines docker_ops + registry queries
- Returns: health_status, restart_count, last_check_at for each project

**MCP Tool:**
```
devps.health.status
```

**Input Schema:**
```json
{
  "project_filter": "string (optional)"
}
```

**Output Schema:**
```json
{
  "projects": [
    {
      "name": "string",
      "status": "running|dead|unhealthy|unknown",
      "restart_count": "integer",
      "last_check": "ISO8601",
      "last_restart": "ISO8601 (optional)"
    }
  ]
}
```

**RBAC:**
- Required Permission: `view_health` (viewer+)

**Side Effects:**
- None (read-only, docker inspect only)

---

### 3.2 Auto-Restart Configuration

**DEVPS Implementation:**
- File: `health_checks.py`
- Components:
  - `RestartRateLimiter`: max 5 restarts/hour per project
  - `ExponentialBackoffTracker`: 30s → 2min → 30min delays
  - Background async task: runs every 30 seconds
  - `alerting.py`: sends email/Slack on failure

**MCP Tool (Read-Only Info):**
```
devps.health.config (resource, not tool)
```

**MCP Tool (Trigger Manual Check):**
```
devps.health.check
```

**Input Schema:**
```json
{
  "project_name": "string (required)"
}
```

**Output Schema:**
```json
{
  "status": "running|dead|unhealthy|unknown",
  "checked_at": "ISO8601"
}
```

**RBAC:**
- Required Permission: `view_health` (viewer+)

**Side Effects:**
- Runs immediate health check (non-blocking)
- Does NOT auto-restart (that's background only)
- Does NOT send alerts

---

## 4. ALERTS

### 4.1 Configure Alerts

**DEVPS Implementation:**
- File: `dashboard.py::update_settings_endpoint()` + registry columns
- DB columns: `alert_email`, `alert_slack`, `alert_enabled`
- Supports: Email + Slack webhook URLs

**MCP Tool:**
```
devps.alerts.configure
```

**Input Schema:**
```json
{
  "project_name": "string (required)",
  "email": "string (optional, email format)",
  "slack": "string (optional, webhook URL)",
  "enabled": "boolean"
}
```

**Output Schema:**
```json
{
  "success": "boolean",
  "project_name": "string"
}
```

**RBAC:**
- Required Permission: `edit_project` (deployer+)
- Deployer can only configure own projects (unless admin)

**Side Effects:**
- ✅ Updates alert_email, alert_slack, alert_enabled in DB
- ✅ No immediate alert sent
- ✅ Alerts activated on next health failure

---

### 4.2 Mute Alerts

**DEVPS Implementation:**
- File: `dashboard.py::mute_alerts_endpoint()` + registry column
- DB column: `alert_muted_until` (ISO8601 timestamp)
- Duration: 1-24 hours

**MCP Tool:**
```
devps.alerts.mute
```

**Input Schema:**
```json
{
  "project_name": "string (required)",
  "hours": "integer (1-24)"
}
```

**Output Schema:**
```json
{
  "success": "boolean",
  "muted_until": "ISO8601"
}
```

**RBAC:**
- Required Permission: `edit_project` (deployer+)

**Side Effects:**
- ✅ Updates alert_muted_until in DB
- ✅ Alerts will not be sent while muted
- ✅ Auto-restart still happens (not affected)

---

### 4.3 Unmute Alerts

**DEVPS Implementation:**
- Implicit: setting alert_muted_until to NULL or past time

**MCP Tool:**
```
devps.alerts.unmute
```

**Input Schema:**
```json
{
  "project_name": "string (required)"
}
```

**Output Schema:**
```json
{
  "success": "boolean"
}
```

**RBAC:**
- Required Permission: `edit_project` (deployer+)

**Side Effects:**
- ✅ Clears alert_muted_until
- ✅ Alerts resume on next health event

---

## 5. EVENTS & AUDIT

### 5.1 Get Project Events

**DEVPS Implementation:**
- File: `registry.py::get_events(project_name, limit)`
- Returns: kind, detail, success, created_at

**MCP Tool:**
```
devps.events.get
```

**Input Schema:**
```json
{
  "project_name": "string (required)",
  "limit": "integer (default: 100)"
}
```

**Output Schema:**
```json
{
  "events": [
    {
      "id": "integer",
      "kind": "deploy|restart|adopt|vhost_installed|etc",
      "detail": "string",
      "success": "boolean",
      "created_at": "ISO8601"
    }
  ]
}
```

**RBAC:**
- Required Permission: `view_events` (viewer+)

**Side Effects:**
- None (read-only)

---

### 5.2 List All Events

**DEVPS Implementation:**
- File: `registry.py::list_events(limit)`
- Returns: global event log across all projects

**MCP Tool:**
```
devps.events.list
```

**Input Schema:**
```json
{
  "limit": "integer (default: 200)"
}
```

**Output Schema:**
```json
{
  "events": [
    {
      "id": "integer",
      "project_name": "string",
      "kind": "string",
      "detail": "string",
      "success": "boolean",
      "created_at": "ISO8601"
    }
  ]
}
```

**RBAC:**
- Required Permission: `view_events` (viewer+)

**Side Effects:**
- None (read-only)

---

## 6. MIGRATIONS

### 6.1 Get Migration Status

**DEVPS Implementation:**
- File: `registry.py::touch_migration()`, `get_migration()`, `list_migrations()`
- Steps: adopted → paralleled → cutover → decommissioned
- Tracks timestamps for each step

**MCP Tool:**
```
devps.migrations.list
```

**Input Schema:**
```json
{
  "filter_status": "string (optional: adopting, paralleled, cutover, decommissioned)"
}
```

**Output Schema:**
```json
{
  "migrations": [
    {
      "project_name": "string",
      "source_description": "string",
      "adopted_at": "ISO8601",
      "paralleled_at": "ISO8601 (optional)",
      "cutover_at": "ISO8601 (optional)",
      "decommissioned_at": "ISO8601 (optional)"
    }
  ]
}
```

**RBAC:**
- Required Permission: `view_project` (viewer+)

**Side Effects:**
- None (read-only)

---

### 6.2 Transition Migration

**DEVPS Implementation:**
- File: `registry.py::touch_migration(name, step, source_description)`
- Steps: adopted → paralleled → cutover → decommissioned

**MCP Tool:**
```
devps.migrations.transition
```

**Input Schema:**
```json
{
  "project_name": "string (required)",
  "step": "string (paralleled|cutover|decommissioned)",
  "source_description": "string (optional)"
}
```

**Output Schema:**
```json
{
  "success": "boolean",
  "project_name": "string"
}
```

**RBAC:**
- Required Permission: `edit_project` (admin only for migrations)

**Side Effects:**
- ✅ Updates migration record with timestamp
- ✅ Logs migration event

---

## 7. USERS

### 7.1 List Users

**DEVPS Implementation:**
- File: `registry.py::list_users()`
- Returns: username, role, created_at, created_by

**MCP Tool:**
```
devps.users.list
```

**Input Schema:**
```json
{}
```

**Output Schema:**
```json
{
  "users": [
    {
      "username": "string",
      "role": "admin|deployer|viewer",
      "created_at": "ISO8601",
      "created_by": "string"
    }
  ]
}
```

**RBAC:**
- Required Permission: `list_users` (admin only)

**Side Effects:**
- None (read-only)

---

### 7.2 Create User

**DEVPS Implementation:**
- File: `dashboard.py::create_user_endpoint()` + `registry.py::create_user()`
- Password: PBKDF2-SHA256 (100,000 iterations)

**MCP Tool:**
```
devps.users.create
```

**Input Schema:**
```json
{
  "username": "string (email format)",
  "password": "string (min 8 chars)",
  "role": "string (admin|deployer|viewer)"
}
```

**Output Schema:**
```json
{
  "success": "boolean",
  "username": "string"
}
```

**RBAC:**
- Required Permission: `create_user` (admin only)

**Side Effects:**
- ✅ Creates user in DB
- ✅ Logs creation event
- ✅ User can log in immediately

---

### 7.3 Update User Role

**DEVPS Implementation:**
- File: `dashboard.py::update_user_role_endpoint()` + `registry.py::update_user_role()`

**MCP Tool:**
```
devps.users.update-role
```

**Input Schema:**
```json
{
  "username": "string (required)",
  "role": "string (admin|deployer|viewer)"
}
```

**Output Schema:**
```json
{
  "success": "boolean",
  "username": "string",
  "new_role": "string"
}
```

**RBAC:**
- Required Permission: `change_user_role` (admin only)

**Side Effects:**
- ✅ Updates user role in DB
- ✅ Logs role change event
- ✅ Takes effect immediately on user's next session/request

---

### 7.4 Delete User

**DEVPS Implementation:**
- File: `dashboard.py::delete_user_endpoint()` + `registry.py::delete_user()`

**MCP Tool:**
```
devps.users.delete
```

**Input Schema:**
```json
{
  "username": "string (required)"
}
```

**Output Schema:**
```json
{
  "success": "boolean"
}
```

**RBAC:**
- Required Permission: `delete_user` (admin only)
- Cannot delete yourself

**Side Effects:**
- ✅ Removes user from DB
- ✅ Logs deletion event
- ✅ User cannot log in anymore

---

## 8. AUTHENTICATION & SESSIONS

### 8.1 Login

**DEVPS Implementation:**
- File: `dashboard.py::login_submit()` + `auth.py::verify_password()`
- Rate limiting: 5 failures per IP (login_throttle.py)

**Note:** Not exposed as MCP tool. MCP Server should use session auth on top.

---

## 9. GITHUB INTEGRATION

### 9.1 Create Repository (Auto-Project)

**DEVPS Implementation:**
- File: `github_ops.py::create_repo()` + `init_repo_with_compose()`
- Process:
  1. GitHub API: create repo
  2. Clone repo
  3. Generate Dockerfile, docker-compose.yml, package.json, index.js
  4. Git commit + push
  5. docker compose up --build

**MCP Tool:**
```
devps.projects.create-auto
```

**Input Schema:**
```json
{
  "name": "string (required, project name)",
  "domain": "string (optional)"
}
```

**Output Schema:**
```json
{
  "name": "string",
  "repo_url": "string",
  "port": "integer",
  "status": "deployed"
}
```

**RBAC:**
- Required Permission: `create_project` (deployer+)

**Side Effects:**
- ✅ Creates GitHub repository
- ✅ Clones + generates starter files
- ✅ Builds + runs Docker container
- ✅ Allocates port
- ✅ Registers in DB

---

## Summary: Tools by Category

### Projects (6 tools)
- `devps.projects.list`
- `devps.projects.get`
- `devps.projects.deploy`
- `devps.projects.adopt`
- `devps.projects.delete`
- `devps.projects.create-auto` (GitHub integration)

### Containers (3 tools)
- `devps.containers.status`
- `devps.containers.restart`
- `devps.containers.logs`

### Health (2 tools)
- `devps.health.status`
- `devps.health.check`

### Alerts (3 tools)
- `devps.alerts.configure`
- `devps.alerts.mute`
- `devps.alerts.unmute`

### Events (2 tools)
- `devps.events.get`
- `devps.events.list`

### Migrations (2 tools)
- `devps.migrations.list`
- `devps.migrations.transition`

### Users (4 tools)
- `devps.users.list`
- `devps.users.create`
- `devps.users.update-role`
- `devps.users.delete`

**Total: 22 Tools**

---

## RESOURCES

Resources are read-only, stateless snapshots suitable for MCP Resource protocol.

### `devps://projects`
Returns all projects (same as `devps.projects.list`)

### `devps://project/{name}`
Returns project details (same as `devps.projects.get`)

### `devps://project/{name}/logs`
Returns recent logs (same as `devps.containers.logs` with default tail)

### `devps://health`
Returns health status for all projects (same as `devps.health.status`)

### `devps://migrations`
Returns all migrations

### `devps://users`
Returns all users (admin only)

---

## MISSING CAPABILITIES (NOT TO BE IMPLEMENTED)

These do NOT exist in DEVPS and should NOT be added:
- FileExecutor (outside scope of DEVPS)
- ProjectAnalyzer (outside scope)
- LLM integration
- Workflow engine
- Mission system
- Repository analysis beyond git metadata

If AgentOS needs these, they belong in AgentOS, not DEVPS.

DEVPS focuses on: **deploy, monitor, restart, manage containers.**

