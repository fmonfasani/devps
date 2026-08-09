"""MCP API token management.

Generate, store, revoke tokens for MCP HTTP authentication.
"""

import secrets
import hashlib
from datetime import datetime, timedelta, UTC
from typing import Optional

from ..db import connect


def _init_tokens_table() -> None:
    """Create devps_mcp_tokens table if it doesn't exist."""
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS devps_mcp_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token_hash TEXT UNIQUE NOT NULL,
                token TEXT NOT NULL,
                username TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                revoked INTEGER DEFAULT 0,
                last_used_at TEXT,
                FOREIGN KEY (username) REFERENCES users(username)
            )
            """
        )


def generate_token(username: str, expires_in_days: int = 30) -> str:
    """Generate a new MCP API token for a user.

    Args:
        username: Username to create token for
        expires_in_days: Days until token expires (default 30)

    Returns:
        New API token (store this in client)

    Raises:
        ValueError: If user doesn't exist
    """
    from .. import registry

    # Verify user exists
    user = registry.get_user(username)
    if not user:
        raise ValueError(f"User {username!r} not found")

    # Initialize table
    _init_tokens_table()

    # Generate random token
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    # Calculate expiry
    created_at = datetime.now(UTC)
    expires_at = created_at + timedelta(days=expires_in_days)

    # Store in database
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO devps_mcp_tokens
            (token_hash, token, username, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (token_hash, token, username, created_at.isoformat(), expires_at.isoformat()),
        )

    return token


def list_tokens(username: str) -> list[dict]:
    """List active tokens for a user.

    Args:
        username: Username

    Returns:
        List of token info (without the token itself)
    """
    _init_tokens_table()

    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, created_at, expires_at, revoked, last_used_at
            FROM devps_mcp_tokens
            WHERE username = ?
            ORDER BY created_at DESC
            """,
            (username,),
        ).fetchall()

    return [dict(r) for r in rows]


def revoke_token(token_id: int) -> None:
    """Revoke a token by ID.

    Args:
        token_id: Token ID from database
    """
    _init_tokens_table()

    with connect() as conn:
        conn.execute(
            "UPDATE devps_mcp_tokens SET revoked = 1 WHERE id = ?",
            (token_id,),
        )


def revoke_all_tokens(username: str) -> None:
    """Revoke all tokens for a user.

    Args:
        username: Username
    """
    _init_tokens_table()

    with connect() as conn:
        conn.execute(
            "UPDATE devps_mcp_tokens SET revoked = 1 WHERE username = ?",
            (username,),
        )


def validate_token(token: str) -> Optional[str]:
    """Validate token and return username.

    Args:
        token: Token to validate

    Returns:
        Username if valid, None otherwise
    """
    if not token:
        return None

    _init_tokens_table()

    # Hash token
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    try:
        with connect() as conn:
            row = conn.execute(
                """
                SELECT username, revoked, expires_at
                FROM devps_mcp_tokens
                WHERE token_hash = ?
                """,
                (token_hash,),
            ).fetchone()

            if not row:
                return None

            # Check if revoked
            if row["revoked"]:
                return None

            # Check if expired
            expires_at = datetime.fromisoformat(row["expires_at"])
            if datetime.now(UTC) > expires_at:
                return None

            # Update last_used_at
            conn.execute(
                "UPDATE devps_mcp_tokens SET last_used_at = ? WHERE token_hash = ?",
                (datetime.now(UTC).isoformat(), token_hash),
            )

            return row["username"]
    except Exception:
        return None
