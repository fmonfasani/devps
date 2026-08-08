"""Password hashing and verification for dashboard authentication."""

import hashlib
import os
import secrets


def hash_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
    """Hash a password using PBKDF2-SHA256.

    Returns (hash_hex, salt_hex).
    """
    if salt is None:
        salt = os.urandom(16)

    hash_bytes = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    return hash_bytes.hex(), salt.hex()


def verify_password(password: str, salt_hex: str, expected_hash_hex: str) -> bool:
    """Verify a password against a stored hash and salt."""
    salt = bytes.fromhex(salt_hex)
    hash_bytes = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    computed_hash_hex = hash_bytes.hex()
    return secrets.compare_digest(computed_hash_hex, expected_hash_hex)
