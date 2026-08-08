#!/bin/bash
set -euo pipefail

DB_PATH="/opt/devps/data/registry.db"

python3 << 'EOF'
import sqlite3

conn = sqlite3.connect("/opt/devps/data/registry.db")
cursor = conn.cursor()

# Add health_status column
try:
    cursor.execute("ALTER TABLE projects ADD COLUMN health_status TEXT DEFAULT 'unknown'")
    print("✓ Added health_status column")
except sqlite3.OperationalError as e:
    if "already exists" in str(e):
        print("✓ health_status column already exists")
    else:
        raise

# Add restart_count column
try:
    cursor.execute("ALTER TABLE projects ADD COLUMN restart_count INTEGER DEFAULT 0")
    print("✓ Added restart_count column")
except sqlite3.OperationalError as e:
    if "already exists" in str(e):
        print("✓ restart_count column already exists")
    else:
        raise

# Add last_health_check_at column
try:
    cursor.execute("ALTER TABLE projects ADD COLUMN last_health_check_at TEXT")
    print("✓ Added last_health_check_at column")
except sqlite3.OperationalError as e:
    if "already exists" in str(e):
        print("✓ last_health_check_at column already exists")
    else:
        raise

# Add last_restart_at column
try:
    cursor.execute("ALTER TABLE projects ADD COLUMN last_restart_at TEXT")
    print("✓ Added last_restart_at column")
except sqlite3.OperationalError as e:
    if "already exists" in str(e):
        print("✓ last_restart_at column already exists")
    else:
        raise

conn.commit()
conn.close()
print("✓ Migration complete")
EOF
