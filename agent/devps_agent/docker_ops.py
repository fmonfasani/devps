"""Thin subprocess wrappers around `docker` / `git`. No Docker SDK — the agent
runs directly on the VPS host, so shelling out is simpler and more legible
than a client library, and matches the existing deploy scripts this replaces.
"""

import json
import subprocess
from pathlib import Path


class CommandError(RuntimeError):
    pass


def run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise CommandError(f"`{' '.join(cmd)}` failed: {result.stderr.strip()}")
    return result


def clone_or_update(repo_url: str, project_dir: Path, git_ref: str) -> str:
    """Clone on first deploy, otherwise fetch + hard-reset onto git_ref.
    Deploy checkouts are never hand-edited, so discarding local drift is safe
    and keeps prod matching exactly what's on git_ref."""
    if not (project_dir / ".git").exists():
        run(["git", "clone", repo_url, str(project_dir)])
    run(["git", "fetch", "origin", git_ref], cwd=project_dir)
    run(["git", "checkout", git_ref], cwd=project_dir)
    run(["git", "reset", "--hard", f"origin/{git_ref}"], cwd=project_dir)
    return run(["git", "rev-parse", "--short", "HEAD"], cwd=project_dir).stdout.strip()


def compose_up(project_dir: Path, compose_file: str, env: dict[str, str]) -> str:
    import os

    result = subprocess.run(
        ["docker", "compose", "-f", compose_file, "up", "-d", "--build"],
        cwd=project_dir,
        capture_output=True,
        text=True,
        env={**os.environ, **env},
        check=False,
    )
    if result.returncode != 0:
        raise CommandError(result.stderr.strip())
    return result.stdout


def compose_restart(project_dir: Path, compose_file: str) -> None:
    run(["docker", "compose", "-f", compose_file, "restart"], cwd=project_dir)


def inspect_container(container_name: str) -> dict | None:
    result = subprocess.run(
        ["docker", "inspect", container_name], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        return None
    return json.loads(result.stdout)[0]


def container_health(container_name: str) -> str:
    info = inspect_container(container_name)
    if info is None:
        return "missing"
    health = info.get("State", {}).get("Health", {}).get("Status")
    if health:
        return health
    return "running" if info.get("State", {}).get("Running") else "stopped"


def container_logs(container_name: str, tail: int) -> str:
    result = subprocess.run(
        ["docker", "logs", "--tail", str(tail), container_name],
        capture_output=True,
        text=True,
        check=False,
    )
    return (result.stdout or "") + (result.stderr or "")
