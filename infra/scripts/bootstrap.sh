#!/usr/bin/env bash
# infra/scripts/bootstrap.sh — one-shot install of the devps agent on the VPS.
# Idempotent. Does NOT touch Coolify, wapsell, or anything else already on
# the box — only creates /opt/devps and a new systemd service on a port
# (9400) confirmed clear in docs/AUDIT.md.
set -euo pipefail

REPO_DIR="${REPO_DIR:-/opt/devps/repo}"
REPO_URL="${REPO_URL:-https://github.com/fmonfasani/devps.git}"
ENV_FILE="/opt/devps/agent.env"

log() { printf '\033[1;36m[bootstrap]\033[0m %s\n' "$*"; }

[[ $EUID -eq 0 ]] || { echo "must run as root" >&2; exit 1; }

mkdir -p /opt/devps/projects /opt/devps/data

if [[ ! -d "${REPO_DIR}/.git" ]]; then
    log "cloning ${REPO_URL}…"
    git clone "${REPO_URL}" "${REPO_DIR}"
else
    log "pulling latest main…"
    git -C "${REPO_DIR}" fetch origin main
    git -C "${REPO_DIR}" reset --hard origin/main
fi

if [[ ! -f "${ENV_FILE}" ]]; then
    log "writing ${ENV_FILE} — fill DEVPS_TOKEN before starting the service"
    cat > "${ENV_FILE}" <<EOF
DEVPS_TOKEN=<CHANGE_ME_run_openssl_rand_-hex_32>
DEVPS_DATA_DIR=/opt/devps/data
DEVPS_PROJECTS_DIR=/opt/devps/projects
DEVPS_PORT_RANGE_START=40000
DEVPS_PORT_RANGE_END=40999
DEVPS_CERTBOT_EMAIL=
EOF
    chmod 600 "${ENV_FILE}"
fi

log "installing python venv…"
if [[ ! -d /opt/devps/venv ]]; then
    python3 -m venv /opt/devps/venv
fi
/opt/devps/venv/bin/pip install -q --upgrade pip
/opt/devps/venv/bin/pip install -q -e "${REPO_DIR}/agent"

log "installing systemd unit…"
install -m 0644 "${REPO_DIR}/infra/systemd/devps-agent.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable devps-agent

if grep -q "CHANGE_ME" "${ENV_FILE}"; then
    log "⚠️  ${ENV_FILE} still has a placeholder token."
    log "    Edit it (openssl rand -hex 32 for DEVPS_TOKEN), then: systemctl start devps-agent"
    exit 1
fi

systemctl restart devps-agent
sleep 2
systemctl --no-pager --full status devps-agent
log "bootstrap done. Agent listening on 127.0.0.1:9400."
log "Smoke test: curl -H \"Authorization: Bearer \$DEVPS_TOKEN\" http://127.0.0.1:9400/health"
