#!/bin/bash
# Create initial admin user for devps dashboard

set -euo pipefail

if [[ $# -lt 2 ]]; then
    echo "Usage: $0 <username> <password>"
    echo "Example: $0 fmonfasani secret-password"
    exit 1
fi

USERNAME="$1"
PASSWORD="$2"
DB_PATH="/opt/devps/data/registry.db"

echo "[admin] creating admin user: $USERNAME"

python3 << EOF
import sqlite3
import sys
sys.path.insert(0, '/opt/devps/repo/agent')

from devps_agent import auth

# Hash password
hash_hex, salt_hex = auth.hash_password("$PASSWORD")

# Create admin user
conn = sqlite3.connect("$DB_PATH")
try:
    conn.execute("""
        INSERT INTO users (username, password_hash, password_salt, role, created_at, created_by)
        VALUES (?, ?, ?, 'admin', datetime('now'), NULL)
    """, ("$USERNAME", hash_hex, salt_hex))
    conn.commit()
    print(f"✓ Admin user '{USERNAME}' created successfully")
except sqlite3.IntegrityError:
    print(f"✗ User '{USERNAME}' already exists")
    sys.exit(1)
finally:
    conn.close()
EOF
