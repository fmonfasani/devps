"""SQLite registry — the single source of truth for what devps knows about."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    name TEXT PRIMARY KEY,
    managed_by TEXT NOT NULL CHECK (managed_by IN ('devps', 'adopted')),
    repo_url TEXT,
    git_ref TEXT,
    git_sha TEXT,
    domain TEXT,
    status TEXT NOT NULL DEFAULT 'unknown',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS project_ports (
    project_name TEXT NOT NULL REFERENCES projects(name) ON DELETE CASCADE,
    service TEXT NOT NULL,
    host_port INTEGER NOT NULL UNIQUE,
    container_port INTEGER NOT NULL,
    PRIMARY KEY (project_name, service)
);

-- Append-only. Never updated or deleted except by the project's own
-- ON DELETE CASCADE — this is the history a status snapshot can't give you
-- (e.g. "this deploy failed twice before it worked").
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_name TEXT NOT NULL REFERENCES projects(name) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    detail TEXT,
    success INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_project_created
    ON events (project_name, created_at);

-- One row per project being migrated off Coolify (or anything else) — the
-- live version of the table in docs/MIGRATION.md. NULL timestamps mean
-- that step hasn't happened yet.
CREATE TABLE IF NOT EXISTS migrations (
    project_name TEXT PRIMARY KEY REFERENCES projects(name) ON DELETE CASCADE,
    source_description TEXT,
    adopted_at TEXT,
    paralleled_at TEXT,
    cutover_at TEXT,
    decommissioned_at TEXT,
    notes TEXT
);
"""


def init_db() -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.executescript(SCHEMA)


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
