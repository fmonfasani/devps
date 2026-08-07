"""Writes/reloads host nginx vhosts and mints certs via certbot.

This runs directly on the VPS host (see infra/systemd/devps-agent.service) —
that's what makes calling `nginx`, `certbot`, and `systemctl` here actually
work, instead of trying to manage the host's nginx from inside a container.
"""

import subprocess

from . import config

_BOOTSTRAP_TEMPLATE = """\
# devps-managed bootstrap vhost for {domain} — serves only the ACME
# challenge so certbot can mint the real cert. Replaced by the full HTTPS
# vhost right after.
server {{
    listen 80;
    listen [::]:80;
    server_name {domain};
    location /.well-known/acme-challenge/ {{
        root {webroot};
    }}
    location / {{
        return 404;
    }}
}}
"""

_VHOST_TEMPLATE = """\
# devps-managed vhost for {domain} -> 127.0.0.1:{port}
server {{
    listen 80;
    listen [::]:80;
    server_name {domain};
    location /.well-known/acme-challenge/ {{
        root {webroot};
    }}
    location / {{
        return 301 https://$host$request_uri;
    }}
}}
server {{
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name {domain};
    ssl_certificate /etc/letsencrypt/live/{domain}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{domain}/privkey.pem;
    add_header Strict-Transport-Security "max-age=15768000" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    location / {{
        proxy_pass http://127.0.0.1:{port};
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }}
}}
"""


class NginxError(RuntimeError):
    pass


def _run(cmd: list[str]) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise NginxError(f"`{' '.join(cmd)}` failed: {result.stderr.strip()}")
    return result.stdout


def _reload() -> None:
    _run(["nginx", "-t"])
    _run(["systemctl", "reload", "nginx"])


def install_vhost(domain: str, port: int) -> None:
    """Idempotent: safe to call again on every redeploy of the same project."""
    available = config.NGINX_SITES_AVAILABLE / domain
    enabled = config.NGINX_SITES_ENABLED / domain
    cert_live = f"/etc/letsencrypt/live/{domain}"

    cert_exists = subprocess.run(["test", "-d", cert_live], check=False).returncode == 0

    if not cert_exists:
        available.write_text(
            _BOOTSTRAP_TEMPLATE.format(domain=domain, webroot=config.CERTBOT_WEBROOT)
        )
        if not enabled.exists():
            enabled.symlink_to(available)
        _reload()
        _run(
            [
                "certbot",
                "certonly",
                "--webroot",
                "-w",
                config.CERTBOT_WEBROOT,
                "-d",
                domain,
                "--non-interactive",
                "--agree-tos",
                "--email",
                config.CERTBOT_EMAIL,
            ]
        )

    available.write_text(
        _VHOST_TEMPLATE.format(domain=domain, port=port, webroot=config.CERTBOT_WEBROOT)
    )
    if not enabled.exists():
        enabled.symlink_to(available)
    _reload()
