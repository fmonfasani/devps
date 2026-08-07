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
