#!/bin/bash
# Migrate devps database schema

set -euo pipefail

DB_PATH="/opt/devps/data/registry.db"

echo "[migrate] backing up registry.db..."
cp "$DB_PATH" "$DB_PATH.backup.$(date +%s)"

echo "[migrate] running migrations..."

python3 << 'EOF'
import sqlite3

conn = sqlite3.connect("/opt/devps/data/registry.db")
conn.execute("PRAGMA foreign_keys = ON")
cursor = conn.cursor()

# Check if users table exists, if not create it
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
if not cursor.fetchone():
    print("[migrate] creating users table...")
    conn.executescript("""
CREATE TABLE users (
    username TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    password_salt TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin', 'deployer', 'viewer')),
    created_at TEXT NOT NULL,
    created_by TEXT
);
""")

# Check if projects table has owner column, if not add it
cursor.execute("PRAGMA table_info(projects)")
columns = [col[1] for col in cursor.fetchall()]
if 'owner' not in columns:
    print("[migrate] adding owner column to projects...")
    conn.execute("ALTER TABLE projects ADD COLUMN owner TEXT REFERENCES users(username)")
if 'created_by' not in columns:
    print("[migrate] adding created_by column to projects...")
    conn.execute("ALTER TABLE projects ADD COLUMN created_by TEXT")

# Check if events table has created_by column, if not add it
cursor.execute("PRAGMA table_info(events)")
columns = [col[1] for col in cursor.fetchall()]
if 'created_by' not in columns:
    print("[migrate] adding created_by column to events...")
    conn.execute("ALTER TABLE events ADD COLUMN created_by TEXT REFERENCES users(username)")

conn.commit()
print("[migrate] done!")
conn.close()
EOF

echo "[migrate] migration complete"
