"""Analyze and parse repository structure for automated deployment."""

import re
import secrets
import subprocess
import tempfile
from pathlib import Path

import yaml


def clone_shallow(repo_url: str, git_ref: str) -> Path:
    """Clone repository with depth 1 to a temporary directory."""
    tmpdir = Path(tempfile.mkdtemp())
    subprocess.run(
        ["git", "clone", "--depth", "1", "--branch", git_ref, repo_url, str(tmpdir)],
        check=True,
        capture_output=True,
    )
    return tmpdir


def parse_compose_services(compose_path: Path) -> dict[str, dict]:
    """Parse docker-compose.yml and extract services with port configuration.

    Returns dict of service configs with container_port, host_port_var, needs_manual_edit.
    """
    with open(compose_path) as f:
        compose = yaml.safe_load(f) or {}

    services = compose.get("services", {})
    result = {}

    port_pattern = re.compile(r"\$\{DEVPS_PORT_([A-Z0-9_]+)(?::-(\d+))?\}:(\d+)")

    for service_name, service_config in services.items():
        if not isinstance(service_config, dict):
            continue

        ports = service_config.get("ports", [])
        container_port = None
        host_port_var = None
        needs_manual_edit = True

        for port_spec in ports:
            if isinstance(port_spec, str):
                match = port_pattern.search(port_spec)
                if match:
                    host_port_var = match.group(1)
                    container_port = int(match.group(3))
                    needs_manual_edit = False
                    break
            elif isinstance(port_spec, dict):
                container_port = port_spec.get("target")
                if container_port:
                    break

        if container_port is None and ports:
            # Try to extract from simple format like "3000:3000"
            for port_spec in ports:
                if isinstance(port_spec, str) and ":" in port_spec:
                    parts = port_spec.split(":")
                    if len(parts) >= 2:
                        try:
                            container_port = int(parts[-1])
                            needs_manual_edit = True
                            break
                        except ValueError:
                            pass

        if container_port is not None:
            result[service_name] = {
                "container_port": container_port,
                "host_port_var": host_port_var,
                "needs_manual_edit": needs_manual_edit,
            }

    return result


def parse_env_example(repo_dir: Path) -> list[str]:
    """Read .env.example and return list of variable names."""
    env_example = repo_dir / ".env.example"
    if not env_example.exists():
        return []

    variables = []
    with open(env_example) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                var_name = line.split("=", 1)[0].strip()
                if var_name:
                    variables.append(var_name)

    return variables


def classify_and_generate(var_names: list[str]) -> dict[str, dict]:
    """Classify variables and generate values for secret-like ones.

    Returns dict of {var_name: {value: str|None, generatable: bool}}
    """
    generatable_suffixes = {
        "PASSWORD",
        "ENCRYPTION_KEY",
        "SESSION_SECRET",
        "JWT_SECRET",
        "AUTH_SECRET",
        "COOKIE_SECRET",
        "CSRF_SECRET",
        "VERIFY_TOKEN",
        "SALT",
    }

    result = {}
    for var_name in var_names:
        is_generatable = False
        value = None

        upper_name = var_name.upper()
        has_secret_suffix = any(
            upper_name.endswith(suffix) for suffix in generatable_suffixes
        )
        if has_secret_suffix or "INTERNAL" in upper_name:
            is_generatable = True

        if is_generatable:
            value = secrets.token_hex(24)

        result[var_name] = {"value": value, "generatable": is_generatable}

    return result
