"""CRUD against the projects/project_ports tables."""

from datetime import UTC, datetime
from typing import Any

from .db import connect


def _now() -> str:
    return datetime.now(UTC).isoformat()


def upsert_project(
    name: str,
    managed_by: str,
    repo_url: str | None = None,
    git_ref: str | None = None,
    git_sha: str | None = None,
    domain: str | None = None,
    status: str = "unknown",
) -> None:
    ts = _now()
    with connect() as conn:
        exists = conn.execute("SELECT 1 FROM projects WHERE name = ?", (name,)).fetchone()
        if exists:
            conn.execute(
                """UPDATE projects
                   SET managed_by = ?, repo_url = ?, git_ref = ?, git_sha = ?,
                       domain = ?, status = ?, updated_at = ?
                   WHERE name = ?""",
                (managed_by, repo_url, git_ref, git_sha, domain, status, ts, name),
            )
        else:
            conn.execute(
                """INSERT INTO projects
                   (name, managed_by, repo_url, git_ref, git_sha,
                    domain, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (name, managed_by, repo_url, git_ref, git_sha, domain, status, ts, ts),
            )


def set_port(name: str, service: str, host_port: int, container_port: int) -> None:
    with connect() as conn:
        conn.execute(
            """INSERT INTO project_ports (project_name, service, host_port, container_port)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(project_name, service) DO UPDATE
               SET host_port = excluded.host_port, container_port = excluded.container_port""",
            (name, service, host_port, container_port),
        )


def _ports_for(conn, name: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """SELECT service, host_port, container_port FROM project_ports
           WHERE project_name = ? ORDER BY service""",
        (name,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_project(name: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM projects WHERE name = ?", (name,)).fetchone()
        if not row:
            return None
        return {**dict(row), "ports": _ports_for(conn, name)}


def list_projects() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM projects ORDER BY name").fetchall()
        return [{**dict(row), "ports": _ports_for(conn, row["name"])} for row in rows]


def delete_project(name: str) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM projects WHERE name = ?", (name,))
