"""Settings read from the environment. No defaults for secrets — fail loudly."""

import os
from pathlib import Path


def _int_env(name: str, default: int) -> int:
    return int(os.environ.get(name, str(default)))


DATA_DIR = Path(os.environ.get("DEVPS_DATA_DIR", "/opt/devps/data"))
DB_PATH = DATA_DIR / "registry.db"
PROJECTS_DIR = Path(os.environ.get("DEVPS_PROJECTS_DIR", "/opt/devps/projects"))

# The one shared credential. Required — the agent refuses to start without it.
BEARER_TOKEN = os.environ["DEVPS_TOKEN"]

# Port range devps owns exclusively. Chosen (see docs/AUDIT.md) to sit clear
# of Coolify's 31000-31999 range and every port already in use on the VPS.
PORT_RANGE_START = _int_env("DEVPS_PORT_RANGE_START", 40000)
PORT_RANGE_END = _int_env("DEVPS_PORT_RANGE_END", 40999)

NGINX_SITES_AVAILABLE = Path(
    os.environ.get("DEVPS_NGINX_SITES_AVAILABLE", "/etc/nginx/sites-available")
)
NGINX_SITES_ENABLED = Path(os.environ.get("DEVPS_NGINX_SITES_ENABLED", "/etc/nginx/sites-enabled"))
CERTBOT_WEBROOT = os.environ.get("DEVPS_CERTBOT_WEBROOT", "/var/www/certbot")
CERTBOT_EMAIL = os.environ.get("DEVPS_CERTBOT_EMAIL", "")
