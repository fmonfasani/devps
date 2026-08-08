# Deployment & Operations

## VPS Setup (One-time)

### Prerequisites

- VPS: Hetzner CPX11 (2 vCPU, 4GB RAM, 40GB SSD)
- IP: 89.167.96.239
- OS: Ubuntu 22.04 LTS
- SSH access as root

### Installation Steps

```bash
# 1. Update system
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3.11 python3.11-venv python3-pip docker.io curl git

# 2. Create devps user (optional, run as root for simplicity)
# sudo useradd -m -s /bin/bash devps

# 3. Create directories
sudo mkdir -p /opt/devps/{data,projects,secrets}
sudo chmod 755 /opt/devps
sudo chmod 700 /opt/devps/secrets

# 4. Create venv
cd /opt/devps
python3.11 -m venv venv
source venv/bin/activate

# 5. Clone repo
git clone https://github.com/fmonfasani/devps.git repo

# 6. Install dependencies
cd repo/agent
pip install -e .

# 7. Create agent.env
cat > /opt/devps/agent.env << EOF
DEVPS_TOKEN=$(python3 -c "import secrets; print(secrets.token_hex(32))")
DEVPS_SESSION_HTTPS_ONLY=true
DEVPS_DATA_DIR=/opt/devps/data
DEVPS_PROJECTS_DIR=/opt/devps/projects
DEVPS_NGINX_SITES_AVAILABLE=/etc/nginx/sites-available
DEVPS_NGINX_SITES_ENABLED=/etc/nginx/sites-enabled
DEVPS_CERTBOT_EMAIL=admin@example.com
EOF

# 8. Create systemd service
sudo tee /etc/systemd/system/devps-agent.service > /dev/null << EOF
[Unit]
Description=devps Agent
After=docker.service
Requires=docker.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/devps
Environment="PATH=/opt/devps/venv/bin"
EnvironmentFile=/opt/devps/agent.env
ExecStart=/opt/devps/venv/bin/uvicorn devps_agent.main:app \
  --host 127.0.0.1 --port 8000 --log-level info
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 9. Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable devps-agent
sudo systemctl start devps-agent

# 10. Verify
sudo systemctl status devps-agent
curl -s http://127.0.0.1:8000/health
```

### Nginx Proxy

```bash
# Install Nginx & Certbot
sudo apt install -y nginx certbot python3-certbot-nginx

# Create devps vhost
sudo tee /etc/nginx/sites-available/devps.webshooks.com > /dev/null << EOF
server {
    listen 80;
    server_name devps.webshooks.com;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Host \$host;
    }
}
EOF

# Enable site
sudo ln -s /etc/nginx/sites-available/devps.webshooks.com /etc/nginx/sites-enabled/

# Test and reload
sudo nginx -t
sudo systemctl reload nginx

# SSL with Certbot
sudo certbot --nginx -d devps.webshooks.com -n --agree-tos -m admin@example.com
```

## Deployment Workflow

### Via GitHub Actions (bootstrap.yml)

```yaml
name: Bootstrap agent on VPS

on:
  workflow_dispatch:

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Deploy to VPS
        uses: appleboy/ssh-action@7eaf76671a0d7eec5d98ee897acda4f968735a17
        with:
          host: ${{ secrets.HETZNER_HOST }}
          username: ${{ secrets.HETZNER_USER }}
          key: ${{ secrets.HETZNER_SSH_KEY }}
          port: ${{ secrets.HETZNER_SSH_PORT }}
          script: |
            cd /opt/devps/repo
            git fetch origin
            git reset --hard origin/main
            
            source /opt/devps/venv/bin/activate
            cd agent
            pip install -e . --upgrade
            pytest ../tests/
            ruff check .
            
            sudo systemctl restart devps-agent
            sleep 2
            sudo systemctl status devps-agent
```

### Manual Deployment

```bash
ssh root@89.167.96.239

# Update code
cd /opt/devps/repo
git fetch origin
git reset --hard origin/main

# Update dependencies
source /opt/devps/venv/bin/activate
cd agent
pip install -e . --upgrade

# Run tests
pytest ../tests/
ruff check .

# Restart service
sudo systemctl restart devps-agent
sleep 2
sudo systemctl status devps-agent

# Verify
curl -s https://devps.webshooks.com/health
```

## Operations

### Health Checks

```bash
# API health
curl -s https://devps.webshooks.com/health | jq .

# Service status
systemctl status devps-agent

# Database integrity
sqlite3 /opt/devps/data/registry.db "SELECT COUNT(*) FROM projects;"

# Logs
sudo journalctl -u devps-agent -n 50 -f
tail -f /var/log/nginx/access.log
```

### Common Tasks

#### Restart Service
```bash
sudo systemctl restart devps-agent
# or graceful reload
sudo systemctl reload devps-agent
```

#### Check Logs
```bash
# Last 50 lines
sudo journalctl -u devps-agent -n 50

# Follow logs
sudo journalctl -u devps-agent -f

# Specific time
sudo journalctl -u devps-agent --since "2026-08-01 10:00" --until "2026-08-01 11:00"
```

#### Manual Config Update
```bash
# Edit agent.env
sudo nano /opt/devps/agent.env

# Restart service to apply
sudo systemctl restart devps-agent
```

#### View Project Logs
```bash
# Container logs
docker logs devps_<project_name>_1

# Docker compose logs
cd /opt/devps/projects/<project_name>
docker compose logs -f

# Last 50 lines
docker compose logs --tail 50
```

### Backups (Manual, automation future)

```bash
# Backup database
cp /opt/devps/data/registry.db /opt/devps/data/registry.db.backup.$(date +%s)

# Backup secrets
tar czf /tmp/devps-secrets.tar.gz /opt/devps/secrets/

# Download to local
scp root@89.167.96.239:/opt/devps/data/registry.db.backup.* ~/.backups/

# Restore
cp /opt/devps/data/registry.db.backup.123456 /opt/devps/data/registry.db
sudo systemctl restart devps-agent
```

### Disaster Recovery

#### Registry Database Corrupted
```bash
# Stop service
sudo systemctl stop devps-agent

# Restore from backup
cp /opt/devps/data/registry.db.backup.123456 /opt/devps/data/registry.db

# Restart
sudo systemctl start devps-agent

# Verify
sqlite3 /opt/devps/data/registry.db "SELECT COUNT(*) FROM projects;"
```

#### Lost Secrets
```bash
# If secrets/*.env lost but projects still running:
# 1. Secrets already passed to containers, they keep running
# 2. To redeploy project:
cd /opt/devps/projects/<project_name>
docker compose down
docker compose up -d  # Will use ENV_FILE again if path exists
# OR manually recreate secrets from external source
```

#### Service Won't Start
```bash
# Check logs
sudo journalctl -u devps-agent -n 100

# Common issues:
# 1. Port 8000 in use: netstat -tlnp | grep 8000
# 2. Permission denied: ls -la /opt/devps/
# 3. Dependency missing: pip install -e agent/
# 4. Config missing: ls /opt/devps/agent.env

# Try manual start (debug mode)
cd /opt/devps
source venv/bin/activate
cd repo/agent
uvicorn devps_agent.main:app --host 127.0.0.1 --port 8000
```

## Monitoring & Alerts

### Current State (Manual)
- Check https://devps.webshooks.com/health
- Review recent deployments in dashboard
- Monitor VPS resource usage

### Future Roadmap
- [ ] Prometheus metrics export
- [ ] Grafana dashboards
- [ ] Slack alerts on deploy failure
- [ ] Email alerts on service down
- [ ] Uptime monitoring (status page)

### Resource Monitoring (Now)

```bash
# CPU & Memory
top -u root | grep devps

# Disk space
df -h /opt/devps

# Docker resources
docker stats

# Network connections
netstat -tlnp | grep 8000  # devps port
netstat -tlnp | grep 80    # nginx http
```

## Security Operations

### GitHub Secrets Required

```
HETZNER_HOST        → 89.167.96.239
HETZNER_USER        → root
HETZNER_SSH_KEY     → private key for SSH access
HETZNER_SSH_PORT    → 22 (default)
```

### IP Allowlist (Optional)

```bash
# Block all except known IPs
sudo ufw allow 22/tcp from <your-ip>
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw default deny incoming
sudo ufw enable
```

### Credential Rotation

**For DEVPS_TOKEN (API Bearer)**:
```bash
# Generate new token
NEW_TOKEN=$(python3 -c "import secrets; print(secrets.token_hex(32))")

# Update agent.env
sudo sed -i "s/DEVPS_TOKEN=.*/DEVPS_TOKEN=$NEW_TOKEN/" /opt/devps/agent.env

# Restart
sudo systemctl restart devps-agent

# Update clients (hzploy, webhooks) with new token
```

**For Dashboard Credentials**:
- Use dashboard setup UI: https://devps.webshooks.com/dashboard/setup
- Or re-run setup-dashboard-credentials workflow

## Incident Response

### Deploy Failed

```bash
# 1. Check logs
sudo journalctl -u devps-agent -n 200 | grep -i error

# 2. Rollback to previous commit
cd /opt/devps/repo
git log --oneline -5
git reset --hard <previous-commit>

# 3. Reinstall deps and restart
source /opt/devps/venv/bin/activate
cd agent
pip install -e .
sudo systemctl restart devps-agent

# 4. Verify
curl -s https://devps.webshooks.com/health
```

### Container Won't Start

```bash
# Check docker-compose logs
cd /opt/devps/projects/<project_name>
docker compose logs -f

# Common issues:
# • Port already in use
# • Docker image not found
# • Environment variable missing
# • Storage permission denied

# Restart container
docker compose restart

# Or recreate
docker compose down
docker compose up -d --build
```

### High Disk Usage

```bash
# Find large files
du -sh /opt/devps/*

# Clean docker images/containers
docker system prune -a --volumes

# Check if registry.db is large
ls -lh /opt/devps/data/registry.db

# If too large, consider archival (future)
```

## Maintenance Schedule

| Task | Frequency | Owner |
|------|-----------|-------|
| Backup registry.db | Daily | Cron (future) |
| Security updates | Weekly | Manual |
| Dependency updates | Monthly | Manual (GitHub Dependabot?) |
| Disk cleanup | Monthly | Manual |
| Full security audit | Quarterly | Manual |

## Runbooks

### Runbook 1: Emergency Service Restart
```
1. SSH to VPS
2. sudo systemctl restart devps-agent
3. Wait 5 seconds
4. curl https://devps.webshooks.com/health
5. If 200 OK → done
6. If error → check journalctl, rollback, repeat
```

### Runbook 2: Database Corruption Recovery
```
1. sudo systemctl stop devps-agent
2. cp /opt/devps/data/registry.db /opt/devps/data/registry.db.corrupted
3. Restore from last known good backup
4. sudo systemctl start devps-agent
5. Verify with SELECT COUNT(*) FROM projects
6. Alert user of potential data loss
```

## Future Ops Improvements

- [ ] Automated backups (every 6 hours)
- [ ] Monitoring dashboard (Grafana)
- [ ] Alerting (Slack/PagerDuty)
- [ ] Log centralization (ELK stack?)
- [ ] Disaster recovery runbook
- [ ] Load testing (if multiple VPS)
- [ ] Auto-scaling (not applicable for single VPS)
