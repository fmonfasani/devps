# MCP Server Phase 3 — HTTP Transport & Security

## Overview

Phase 3 adds HTTP transport for remote connections (AgentOS → DEVPS MCP Server).

Complements Phase 1-2:
- ✅ Phase 1: Protocol (stdio)
- ✅ Phase 2: 22 Tools
- ✅ Phase 3: HTTP + Security

---

## Transport Architecture

### Stdio (Local Dev)

```
AgentOS (local machine)
    ↓ subprocess (stdin/stdout)
MCP Server (stdio)
```

**Use case:** Development, testing, same machine

**Run:**
```bash
python -m devps_agent.mcp.server --transport stdio
```

### HTTP (Remote Production)

```
AgentOS (remote machine, e.g., VPS2)
    ↓ HTTPS
MCP Server (HTTP) on DEVPS VPS
    ↓
Docker, registry, health checks
```

**Use case:** Production, different machines, firewall-safe

**Run:**
```bash
python -m devps_agent.mcp.server --transport http --port 9500
```

---

## Files Added

### Core

- `mcp/transport.py` - Transport abstraction (stdio + HTTP)
- `mcp/http_client.py` - HTTP client for remote connections

### Updated

- `mcp/server.py` - CLI support for both transports

---

## Running MCP Server

### Option 1: Stdio (Default, Local)

```bash
cd agent

# Anonymous mode
python -m devps_agent.mcp.server

# With authenticated user
python -m devps_agent.mcp.server --user admin@example.com
```

### Option 2: HTTP (Remote)

```bash
cd agent

# Listen on localhost:9500
python -m devps_agent.mcp.server --transport http --port 9500

# Listen on all interfaces (for remote access)
python -m devps_agent.mcp.server --transport http --port 9500
```

### Option 3: Systemd Service (Production)

```ini
# /etc/systemd/system/devps-mcp.service
[Unit]
Description=DEVPS MCP Server
After=network.target

[Service]
Type=simple
User=devps
WorkingDirectory=/opt/devps
ExecStart=/usr/bin/python -m devps_agent.mcp.server --transport http --port 9500
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Start:
```bash
systemctl start devps-mcp
systemctl enable devps-mcp
```

---

## HTTP API

### Endpoint: POST /mcp/call

Execute MCP tool via HTTP.

**Request:**
```json
POST /mcp/call HTTP/1.1
Authorization: Bearer <token>
Content-Type: application/json

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
  "content": "{\"projects\": [...]}"
}
```

### Endpoint: GET /mcp/health

Health check.

**Response:**
```json
{
  "status": "ok"
}
```

---

## Authentication

### Current Implementation

**Token validation is stubbed** (`_validate_token()` returns None).

You need to implement token validation. Options:

#### Option 1: Session Cookies

Validate existing DEVPS session:
```python
async def _validate_token(self, token: str) -> Optional[str]:
    # Decode session cookie
    session_id = decode_signed_cookie(token)
    
    # Lookup user from session storage
    return get_user_from_session(session_id)
```

#### Option 2: JWT

Issue JWTs:
```python
async def _validate_token(self, token: str) -> Optional[str]:
    # Verify JWT signature
    payload = jwt.decode(token, SECRET_KEY)
    return payload.get("username")
```

#### Option 3: API Keys

Store keys in database:
```python
async def _validate_token(self, token: str) -> Optional[str]:
    # Lookup API key
    key_record = registry.get_api_key(token)
    return key_record.username if key_record else None
```

**TODO:** Implement authentication strategy.

---

## Security Considerations

### HTTPS Required

Always use HTTPS in production:

```bash
# Proxy through Nginx
location /mcp/ {
    proxy_pass http://127.0.0.1:9500;
    proxy_set_header Authorization $http_authorization;
}

# Enable SSL
listen 443 ssl;
ssl_certificate /etc/letsencrypt/live/devps.example.com/fullchain.pem;
ssl_certificate_key /etc/letsencrypt/live/devps.example.com/privkey.pem;
```

### Rate Limiting

Prevent brute force on /mcp/call:

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/mcp/call")
@limiter.limit("100/minute")
async def mcp_call(...):
    ...
```

### Token Expiry

Short-lived tokens:

```python
# Token expires after 1 hour
token = generate_jwt(username="admin", exp=time() + 3600)
```

### Audit Logging

Log all tool calls:

```python
async def mcp_call(...):
    logger.info(f"Tool call: {request['params']['name']} by {username}")
    response = await self.server.handle_request(request)
    logger.info(f"Result: {response['success']}")
```

---

## Client Usage

### Python (Async)

```python
from devps_agent.mcp.http_client import HTTPMCPClient
import asyncio

async def main():
    client = HTTPMCPClient(
        base_url="https://devps.example.com",
        token="bearer-token-here",
    )
    
    try:
        # List tools
        response = await client.list_tools()
        print(f"Tools: {response['tools']}")
        
        # Call tool
        response = await client.call_tool("devps.projects.list")
        projects = json.loads(response["content"])
        print(f"Projects: {projects}")
    finally:
        await client.close()

asyncio.run(main())
```

### cURL

```bash
# List tools
curl -H "Authorization: Bearer $TOKEN" \
  https://devps.example.com/mcp/call \
  -d '{"method": "list_tools"}'

# Call tool
curl -H "Authorization: Bearer $TOKEN" \
  https://devps.example.com/mcp/call \
  -d '{
    "method": "call_tool",
    "params": {
      "name": "devps.projects.list",
      "arguments": {}
    }
  }'
```

### JavaScript/Node.js

```javascript
const response = await fetch('https://devps.example.com/mcp/call', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    method: 'call_tool',
    params: {
      name: 'devps.projects.list',
      arguments: {}
    }
  })
});

const data = await response.json();
console.log(data);
```

---

## Integration with Nginx

### Reverse Proxy Setup

```nginx
upstream devps_mcp {
    server 127.0.0.1:9500;
}

server {
    listen 443 ssl;
    server_name devps.example.com;

    ssl_certificate /etc/letsencrypt/live/devps.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/devps.example.com/privkey.pem;

    location /mcp/ {
        proxy_pass http://devps_mcp;
        proxy_set_header Authorization $http_authorization;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        
        # WebSocket support (future)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    location / {
        proxy_pass http://127.0.0.1:9400;  # FastAPI dashboard
    }
}
```

---

## Environment Variables

```bash
# Optional: configure via env vars
export DEVPS_MCP_TRANSPORT=http
export DEVPS_MCP_PORT=9500
export DEVPS_MCP_AUTH_USER=admin@example.com
```

---

## Testing

### Local Test (Stdio)

```bash
# Terminal 1: Start server
python -m devps_agent.mcp.server --user admin@example.com

# Terminal 2: Send request
echo '{"method": "list_tools"}' | python -m devps_agent.mcp.server --user admin@example.com

# Alternative: Use test client
python -m devps_agent.mcp.client
```

### Remote Test (HTTP)

```bash
# Terminal 1: Start server
python -m devps_agent.mcp.server --transport http --port 9500

# Terminal 2: Test HTTP
curl -X POST http://localhost:9500/mcp/call \
  -H "Authorization: Bearer dummy" \
  -H "Content-Type: application/json" \
  -d '{"method": "list_tools"}'
```

---

## Performance Notes

### Stdio

- No network overhead
- Sequential processing
- Good for: local development, testing

### HTTP

- Network latency (~10-100ms)
- Concurrent requests (async)
- Scalable
- Good for: production, remote connections

---

## Next Steps (Phase 4 - Optional)

- WebSocket transport (streaming logs)
- API key management UI
- Token dashboard
- Rate limiting UI
- Metrics/monitoring

---

## Known Limitations

1. **Authentication not implemented** - Token validation is stubbed
2. **No rate limiting** - Should add `slowapi` middleware
3. **No audit logging** - Should log all tool calls
4. **No metrics** - Should expose Prometheus metrics
5. **No WebSocket** - HTTP polling only

---

## Summary

Phase 3 enables:
- ✅ Local development (stdio)
- ✅ Remote production (HTTP)
- ✅ Secure transport (HTTPS via Nginx)
- ✅ Client libraries (Python, cURL, JS)

**TODO:** Implement token authentication strategy before deploying to production.

