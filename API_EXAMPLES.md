# devps API Examples

Ejemplos de cómo usar la API REST de devps directamente (sin CLI).

**Base URL**: `https://devps.webshooks.com`  
**Auth**: `Authorization: Bearer <DEVPS_TOKEN>`

## 1. List Projects

```bash
curl -H "Authorization: Bearer <token>" \
  https://devps.webshooks.com/projects

# Response:
# [
#   {
#     "name": "myapp",
#     "managed_by": "devps",
#     "repo_url": "https://github.com/user/myapp.git",
#     "git_ref": "main",
#     "git_sha": "abc123",
#     "domain": "myapp.com",
#     "status": "deployed",
#     "created_at": "2026-08-07T10:00:00",
#     "updated_at": "2026-08-07T10:05:00",
#     "ports": [
#       {
#         "service": "web",
#         "host_port": 40001,
#         "container_port": 3000
#       }
#     ],
#     "last_event": {
#       "kind": "deploy",
#       "success": true,
#       "created_at": "2026-08-07T10:05:00"
#     }
#   }
# ]
```

## 2. Get Single Project

```bash
curl -H "Authorization: Bearer <token>" \
  https://devps.webshooks.com/projects/myapp

# Response:
# {...same structure as above...}
```

## 3. Deploy Project

```bash
curl -X POST \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/user/myapp.git",
    "git_ref": "main",
    "services": {
      "web": 3000,
      "api": 8000
    },
    "primary_service": "web",
    "domain": "myapp.com",
    "compose_file": "docker-compose.yml",
    "env_file": "/opt/devps/secrets/myapp.env"
  }' \
  https://devps.webshooks.com/projects/myapp/deploy

# Response:
# {
#   "name": "myapp",
#   "status": "deployed",
#   "git_sha": "abc123def456...",
#   "ports": [
#     {"service": "web", "host_port": 40001, "container_port": 3000},
#     {"service": "api", "host_port": 40002, "container_port": 8000}
#   ],
#   ...
# }
```

### Deploy Request Schema

```json
{
  "repo_url": "string (required)",
  "git_ref": "string (default: main)",
  "compose_file": "string (default: docker-compose.yml)",
  "services": {
    "service_name": 3000,
    "another_service": 8000
  },
  "primary_service": "string (required if domain is set)",
  "domain": "string (optional)",
  "env_file": "string (optional, path on VPS)",
}
```

## 4. Adopt Existing Container

Registrar un container ya corriendo (ej: Coolify) bajo devps.

```bash
curl -X POST \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "container_name": "coolify_myapp_1",
    "domain": "myapp.com"
  }' \
  https://devps.webshooks.com/projects/myapp/adopt

# Response:
# {
#   "name": "myapp",
#   "managed_by": "adopted",
#   "status": "adopted",
#   "ports": [
#     {"service": "main", "host_port": 3000, "container_port": 3000}
#   ],
#   ...
# }
```

## 5. Restart Project

```bash
curl -X POST \
  -H "Authorization: Bearer <token>" \
  https://devps.webshooks.com/projects/myapp/restart

# Response:
# {"status": "restarted"}
```

## 6. View Logs

```bash
curl -H "Authorization: Bearer <token>" \
  'https://devps.webshooks.com/projects/myapp/logs?tail=200'

# Response:
# {
#   "logs": "..."
# }
```

## 7. View Events

```bash
curl -H "Authorization: Bearer <token>" \
  'https://devps.webshooks.com/projects/myapp/events?limit=100'

# Response:
# [
#   {
#     "id": 1,
#     "kind": "deploy",
#     "detail": "git_sha=abc123 ports={web: 40001}",
#     "success": true,
#     "created_at": "2026-08-07T10:05:00"
#   },
#   ...
# ]
```

## 8. Get Migration Status

```bash
curl -H "Authorization: Bearer <token>" \
  https://devps.webshooks.com/projects/myapp/migration

# Response:
# {
#   "project_name": "myapp",
#   "source_description": "container coolify_myapp_1",
#   "adopted_at": "2026-08-01T10:00:00",
#   "paralleled_at": "2026-08-02T10:00:00",
#   "cutover_at": "2026-08-03T10:00:00",
#   "decommissioned_at": null,
#   "notes": "migrated successfully"
# }
```

## 9. Update Migration Step (Manual)

```bash
curl -X POST \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "step": "decommissioned",
    "notes": "old server turned off 2026-08-05"
  }' \
  https://devps.webshooks.com/projects/myapp/migration

# Response:
# {...migration object...}
```

## 10. Deregister Project

Remover del registry sin parar containers.

```bash
curl -X DELETE \
  -H "Authorization: Bearer <token>" \
  https://devps.webshooks.com/projects/myapp

# Response:
# {"status": "deregistered"}
```

## Error Responses

### 401 Unauthorized
```json
{"detail": "Invalid token"}
```

### 404 Not Found
```json
{"detail": "not found"}
```

### 502 Bad Gateway
```json
{"detail": "git error: fatal: repository not found"}
```
or
```json
{"detail": "docker compose failed: service web not defined"}
```

## Public Endpoints (No Auth Required)

### Health Check

```bash
curl https://devps.webshooks.com/health

# Response:
# {"status": "ok"}
```

### Metadata

```bash
curl https://devps.webshooks.com/meta

# Response:
# {
#   "version": "0.1.0",
#   "uptime_seconds": 123456
# }
```

## Advanced Examples

### Python Script: Deploy and Wait for Logs

```python
#!/usr/bin/env python3
import json
import time
import urllib.request

DEVPS_URL = "https://devps.webshooks.com"
TOKEN = "your_token"

def call_api(method, path, data=None):
    req = urllib.request.Request(
        f"{DEVPS_URL}{path}",
        data=json.dumps(data).encode() if data else None,
        method=method,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json"
        }
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

# Deploy
print("Deploying myapp...")
result = call_api("POST", "/projects/myapp/deploy", {
    "repo_url": "https://github.com/user/myapp.git",
    "services": {"web": 3000},
    "primary_service": "web",
    "domain": "myapp.com"
})
print(f"✅ Deploy started, sha: {result['git_sha']}")

# Wait and check logs
for i in range(5):
    time.sleep(5)
    logs = call_api("GET", "/projects/myapp/logs?tail=20")
    if "started" in logs["logs"].lower():
        print(f"✅ Service started!")
        break
    print(f"  Waiting... ({i+1}/5)")
    print(logs["logs"][-200:])  # Last 200 chars
```

### Bash Script: Batch Deploy

```bash
#!/bin/bash

TOKEN="your_token"
DEVPS_URL="https://devps.webshooks.com"

deploy_project() {
    local name=$1
    local repo=$2
    local domain=$3
    
    echo "Deploying $name..."
    
    curl -s -X POST \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -d "{
        \"repo_url\": \"$repo\",
        \"services\": {\"web\": 3000},
        \"primary_service\": \"web\",
        \"domain\": \"$domain\"
      }" \
      $DEVPS_URL/projects/$name/deploy | jq .
    
    echo "✅ $name deployed"
}

# Deploy multiple projects
deploy_project "blog" "https://github.com/user/blog.git" "blog.example.com"
deploy_project "api" "https://github.com/user/api.git" "api.example.com"
deploy_project "admin" "https://github.com/user/admin.git" "admin.example.com"

echo "✅ All projects deployed!"
```

### GitHub Actions: Deploy on Push

```yaml
name: Deploy to devps

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Deploy via devps API
        run: |
          curl -X POST \
            -H "Authorization: Bearer ${{ secrets.DEVPS_TOKEN }}" \
            -H "Content-Type: application/json" \
            -d '{
              "repo_url": "${{ github.repository }}",
              "git_ref": "${{ github.ref }}",
              "services": {"web": 3000},
              "primary_service": "web",
              "domain": "myapp.com"
            }' \
            https://devps.webshooks.com/projects/myapp/deploy
```

## Rate Limiting

**Current**: No rate limiting on API (future: 100 req/min per token)

## Versioning

API es v0 (unstable). Breaking changes may happen before v1.0.

Versioning strategy (future):
- `v1/projects` — stable
- `v2/projects` — breaking changes
