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
    owner: str | None = None,
    created_by: str | None = None,
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
                    domain, status, created_at, updated_at, owner, created_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (name, managed_by, repo_url, git_ref, git_sha, domain, status, ts, ts, owner, created_by),
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


def _last_event_for(conn, name: str) -> dict[str, Any] | None:
    row = conn.execute(
        """SELECT kind, success, created_at FROM events
           WHERE project_name = ? ORDER BY id DESC LIMIT 1""",
        (name,),
    ).fetchone()
    return dict(row) if row else None


def get_project(name: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM projects WHERE name = ?", (name,)).fetchone()
        if not row:
            return None
        return {
            **dict(row),
            "ports": _ports_for(conn, name),
            "last_event": _last_event_for(conn, name),
        }


def list_projects() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM projects ORDER BY name").fetchall()
        return [
            {
                **dict(row),
                "ports": _ports_for(conn, row["name"]),
                "last_event": _last_event_for(conn, row["name"]),
            }
            for row in rows
        ]


def delete_project(name: str) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM projects WHERE name = ?", (name,))


# --- events -----------------------------------------------------------------


def log_event(project_name: str, kind: str, detail: str | None, success: bool) -> None:
    with connect() as conn:
        conn.execute(
            """INSERT INTO events (project_name, kind, detail, success, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (project_name, kind, detail, int(success), _now()),
        )


def get_events(project_name: str, limit: int = 100) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """SELECT id, kind, detail, success, created_at FROM events
               WHERE project_name = ? ORDER BY id DESC LIMIT ?""",
            (project_name, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def list_events(limit: int = 200) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """SELECT id, project_name, kind, detail, success, created_at FROM events
               ORDER BY id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


# --- migrations ---------------------------------------------------------


_MIGRATION_STEP_COLUMNS = {
    "adopted": "adopted_at",
    "paralleled": "paralleled_at",
    "cutover": "cutover_at",
    "decommissioned": "decommissioned_at",
}


def touch_migration(
    name: str,
    step: str,
    source_description: str | None = None,
    notes: str | None = None,
) -> None:
    """Stamp one step of a migration (adopted/paralleled/cutover/decommissioned)
    with the current time. Creates the row on first call. Never overwrites a
    step that's already stamped — steps only move forward."""
    column = _MIGRATION_STEP_COLUMNS[step]
    ts = _now()
    with connect() as conn:
        exists = conn.execute("SELECT 1 FROM migrations WHERE project_name = ?", (name,)).fetchone()
        if not exists:
            conn.execute(
                "INSERT INTO migrations (project_name, source_description) VALUES (?, ?)",
                (name, source_description),
            )
        conn.execute(
            f"UPDATE migrations SET {column} = COALESCE({column}, ?) WHERE project_name = ?",  # noqa: S608 — column comes from the fixed dict above, never from user input
            (ts, name),
        )
        if source_description is not None:
            conn.execute(
                "UPDATE migrations SET source_description = ? WHERE project_name = ?",
                (source_description, name),
            )
        if notes is not None:
            conn.execute("UPDATE migrations SET notes = ? WHERE project_name = ?", (notes, name))


def get_migration(name: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM migrations WHERE project_name = ?", (name,)).fetchone()
        return dict(row) if row else None


def list_migrations() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM migrations ORDER BY project_name").fetchall()
        return [dict(r) for r in rows]


# --- users -------------------------------------------------------------------


def create_user(username: str, password_hash: str, password_salt: str, role: str, created_by: str | None = None) -> None:
    """Create a new user.

    Args:
        username: Username (unique)
        password_hash: Hashed password (PBKDF2-SHA256)
        password_salt: Salt (hex string)
        role: User role (admin, deployer, viewer)
        created_by: Username of who created this user
    """
    ts = _now()
    with connect() as conn:
        conn.execute(
            """INSERT INTO users (username, password_hash, password_salt, role, created_at, created_by)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (username, password_hash, password_salt, role, ts, created_by),
        )


def get_user(username: str) -> dict[str, Any] | None:
    """Get user by username."""
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return dict(row) if row else None


def list_users() -> list[dict[str, Any]]:
    """List all users (excluding password hashes for security)."""
    with connect() as conn:
        rows = conn.execute("SELECT username, role, created_at, created_by FROM users ORDER BY username").fetchall()
        return [dict(r) for r in rows]


def update_user_role(username: str, new_role: str) -> None:
    """Update user role."""
    with connect() as conn:
        conn.execute("UPDATE users SET role = ? WHERE username = ?", (new_role, username))


def delete_user(username: str) -> None:
    """Delete a user (orphans their projects)."""
    with connect() as conn:
        # Set owner to NULL for projects owned by this user
        conn.execute("UPDATE projects SET owner = NULL WHERE owner = ?", (username,))
        # Set created_by to NULL for events created by this user
        conn.execute("UPDATE events SET created_by = NULL WHERE created_by = ?", (username,))
        # Delete the user
        conn.execute("DELETE FROM users WHERE username = ?", (username,))
