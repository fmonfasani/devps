# MCP Server Deployment Guide

## Deployment Architecture

```
AgentOS (remote machine)
    │
    └─→ HTTPS/TLS
         │
       Nginx (reverse proxy)
         │
       MCP Server (HTTP on 127.0.0.1:9500)
         │
    ┌────┴────┬────────┬──────────┐
    │          │        │          │
  Docker  Registry  Health   GitHub
  Daemon     DB    Checks    API
```

---

## Prerequisites

- VPS with Ubuntu 24.04 (or similar)
- Docker + Docker Compose
- Nginx
- Python 3.11+
- Git
- SSL certificate (Let's Encrypt via Certbot)

---

## Step 1: Prepare VPS

```bash
# SSH to VPS
ssh root@<VPS_IP>

# Update system
apt update && apt upgrade -y

# Install dependencies
apt install -y python3.11 python3-pip python3-venv \
    docker.io docker-compose nginx certbot python3-certbot-nginx \
    git curl

# Add current user to docker group
usermod -aG docker $USER
newgrp docker

# Create devps directory
mkdir -p /opt/devps
cd /opt/devps
```

---

## Step 2: Deploy DEVPS Code

```bash
# Clone repository
git clone https://github.com/fmonfasani/devps.git
cd devps/agent

# Create Python virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -e .

# Initialize database (creates tables)
python -c "from devps_agent.db import connect; connect()"
python -c "from devps_agent.mcp.tokens import _init_tokens_table; _init_tokens_table()"
```

---

## Step 3: Configure MCP Server Service

Create systemd service:

```bash
sudo tee /etc/systemd/system/devps-mcp.service > /dev/null <<EOF
[Unit]
Description=DEVPS MCP Server (HTTP)
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/devps/devps/agent
Environment="PATH=/opt/devps/devps/agent/venv/bin"
ExecStart=/opt/devps/devps/agent/venv/bin/python -m devps_agent.mcp.server --transport http --port 9500
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable devps-mcp
sudo systemctl start devps-mcp

# Check status
sudo systemctl status devps-mcp
```

---

## Step 4: Configure Nginx Reverse Proxy

```bash
sudo tee /etc/nginx/sites-available/devps-mcp > /dev/null <<EOF
upstream devps_mcp {
    server 127.0.0.1:9500;
}

server {
    listen 80;
    server_name devps.example.com;

    # Redirect HTTP to HTTPS
    return 301 https://\$server_name\$request_uri;
}

server {
    listen 443 ssl http2;
    server_name devps.example.com;

    # SSL certificates (Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/devps.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/devps.example.com/privkey.pem;

    # Strong SSL settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "SAMEORIGIN" always;

    location /mcp/ {
        proxy_pass http://devps_mcp;

        # Headers
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header Authorization \$http_authorization;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;

        # Buffering
        proxy_buffering off;
    }

    location /health {
        proxy_pass http://devps_mcp;
    }
}
EOF

# Enable site
sudo ln -sf /etc/nginx/sites-available/devps-mcp /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Test Nginx config
sudo nginx -t

# Restart Nginx
sudo systemctl restart nginx
```

---

## Step 5: SSL Certificate (Let's Encrypt)

```bash
# Get certificate
sudo certbot certonly --nginx -d devps.example.com

# Auto-renew (already configured by certbot)
sudo systemctl enable certbot.timer

# Verify
sudo systemctl status certbot.timer
```

---

## Step 6: Create MCP API Tokens

Users can generate tokens via CLI:

```bash
# Log in to VPS
ssh root@<VPS_IP>

# Enter Python environment
cd /opt/devps/devps/agent
source venv/bin/activate
python

# Generate token for a user
from devps_agent.mcp.tokens import generate_token

token = generate_token("admin@example.com", expires_in_days=30)
print(f"Token: {token}")
```

Or integrate into dashboard (future enhancement):

```python
# In dashboard.py
@router.post("/dashboard/api/mcp-token/generate")
async def generate_mcp_token(request: Request):
    user = _get_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, 401)
    
    from .mcp.tokens import generate_token
    token = generate_token(user["username"])
    return JSONResponse({"token": token})
```

---

## Step 7: Verify Deployment

```bash
# Test MCP server health
curl https://devps.example.com/health

# Test tool discovery (with token)
curl -X POST https://devps.example.com/mcp/call \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"method": "list_tools"}'

# Test tool call
curl -X POST https://devps.example.com/mcp/call \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "method": "call_tool",
    "params": {
      "name": "devps.projects.list",
      "arguments": {}
    }
  }'
```

---

## Step 8: AgentOS Configuration

Configure AgentOS to use DEVPS MCP Server:

**Option 1: Environment Variable**
```bash
export DEVPS_MCP_SERVER=https://devps.example.com
export DEVPS_MCP_TOKEN=<your-token>
```

**Option 2: Config File**
```yaml
# ~/.agentos/config.yaml
mcp_servers:
  devps:
    url: https://devps.example.com
    token: <your-token>
```

**Option 3: Code**
```python
from devps_agent.mcp.http_client import HTTPMCPClient

client = HTTPMCPClient(
    base_url="https://devps.example.com",
    token="<your-token>"
)

# Use client...
```

---

## Monitoring

### Logs

```bash
# MCP Server logs
sudo journalctl -u devps-mcp -f

# Nginx logs
sudo tail -f /var/log/nginx/error.log
sudo tail -f /var/log/nginx/access.log

# Combined
sudo journalctl -u devps-mcp -u nginx -f
```

### Performance

```bash
# Check service status
sudo systemctl status devps-mcp

# Check resource usage
ps aux | grep "devps_agent.mcp.server"

# Disk usage
du -sh /opt/devps
df -h /opt/devps
```

---

## Maintenance

### Restart Service

```bash
sudo systemctl restart devps-mcp
```

### Update Code

```bash
cd /opt/devps/devps
git pull origin main

# Restart service
sudo systemctl restart devps-mcp
```

### Backup Database

```bash
# Backup SQLite DB
cp /opt/devps/data/registry.db /opt/devps/backups/registry.db.$(date +%Y%m%d)
```

### Token Management

```bash
python -c "
from devps_agent.mcp.tokens import list_tokens, revoke_token, revoke_all_tokens

# List tokens for user
tokens = list_tokens('admin@example.com')
print(tokens)

# Revoke specific token
revoke_token(1)

# Revoke all tokens for user
revoke_all_tokens('admin@example.com')
"
```

---

## Troubleshooting

### MCP Server won't start

```bash
# Check logs
sudo journalctl -u devps-mcp -n 50

# Verify Python env
/opt/devps/devps/agent/venv/bin/python --version

# Test directly
cd /opt/devps/devps/agent
source venv/bin/activate
python -m devps_agent.mcp.server --transport http --port 9500
```

### Nginx returning 502

```bash
# Check if MCP server is running
curl http://127.0.0.1:9500/health

# Check Nginx config
sudo nginx -t

# Check Nginx logs
sudo tail -f /var/log/nginx/error.log
```

### Authentication failing

```bash
# Verify token exists and is not revoked
cd /opt/devps/devps/agent
source venv/bin/activate
python -c "
from devps_agent.mcp.tokens import validate_token
result = validate_token('YOUR_TOKEN')
print(f'Valid: {result}')
"
```

### SSL certificate issues

```bash
# Renew certificate manually
sudo certbot renew --force-renewal

# Check certificate expiry
sudo certbot certificates
```

---

## Security Checklist

- [ ] SSL/TLS enabled (HTTPS only)
- [ ] Firewall rules (only allow necessary ports)
- [ ] API tokens generated and stored securely
- [ ] Nginx security headers configured
- [ ] Database backups automated
- [ ] Logs monitored
- [ ] Auto-renewal of SSL certificates
- [ ] Rate limiting considered (optional: add slowapi)

---

## Performance Tuning

### Nginx Buffer Settings

```nginx
proxy_buffer_size 128k;
proxy_buffers 4 256k;
proxy_busy_buffers_size 256k;
```

### Connection Pooling

```python
# In HTTPTransport
httpx.AsyncClient(
    limits=httpx.Limits(
        max_connections=100,
        max_keepalive_connections=20,
    )
)
```

### Database Optimization

```sql
-- Add indexes for common queries
CREATE INDEX IF NOT EXISTS idx_tokens_username ON devps_mcp_tokens(username);
CREATE INDEX IF NOT EXISTS idx_tokens_expires ON devps_mcp_tokens(expires_at);
```

---

## Rollback

If deployment fails:

```bash
# Revert to previous version
cd /opt/devps/devps
git revert HEAD
source venv/bin/activate
pip install -e .

# Restart service
sudo systemctl restart devps-mcp
```

---

## Summary

✅ MCP Server deployed on production VPS  
✅ HTTPS + SSL/TLS enabled  
✅ Nginx reverse proxy configured  
✅ API token authentication implemented  
✅ Monitoring and logging in place  
✅ Ready for AgentOS integration  

**Next:** Configure AgentOS to connect to DEVPS MCP Server.

