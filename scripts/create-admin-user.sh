#!/bin/bash
set -euo pipefail

DB_PATH="/opt/devps/data/registry.db"
USERNAME="fmonfasani@gmail.com"
PASSWORD="Kara3010"

python3 << 'EOF'
import sqlite3
import hashlib
import os
import binascii

username = "fmonfasani@gmail.com"
password = "Kara3010"
db_path = "/opt/devps/data/registry.db"
iterations = 100000

salt = os.urandom(16)
salt_hex = binascii.hexlify(salt).decode()

hash_obj = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
hash_hex = binascii.hexlify(hash_obj).decode()

conn = sqlite3.connect(db_path)
conn.execute("PRAGMA foreign_keys = ON")
conn.execute("DELETE FROM users WHERE username = ?", (username,))
conn.commit()
conn.execute(
    "INSERT INTO users (username, password_hash, password_salt, role, created_at, created_by) VALUES (?, ?, ?, ?, datetime('now'), NULL)",
    (username, hash_hex, salt_hex, 'admin')
)
conn.commit()
print("OK: Admin user created")
conn.close()
EOF
