"""User management tools — thin adapters to registry.py."""

import hashlib
import os
import binascii
from typing import Any

from ... import registry
from ..context import MCPContext
from . import register_tool


async def _list_users(context: MCPContext, **kwargs) -> dict[str, Any]:
    """List all users.

    Admin only.
    """
    context.require_permission("list_users")

    users = registry.list_users()

    return {
        "users": users,
    }


async def _create_user(
    context: MCPContext,
    username: str,
    password: str,
    role: str = "viewer",
    **kwargs
) -> dict[str, Any]:
    """Create a new user.

    Admin only.
    """
    context.require_permission("create_user")

    # Validate inputs
    if not username or not password:
        raise ValueError("Username and password required")

    if role not in ["admin", "deployer", "viewer"]:
        raise ValueError(f"Invalid role: {role!r}")

    # Check if user exists
    if registry.get_user(username):
        raise ValueError(f"User {username!r} already exists")

    # Hash password (PBKDF2-SHA256, 100k iterations)
    salt = os.urandom(16)
    salt_hex = binascii.hexlify(salt).decode()
    hash_obj = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    hash_hex = binascii.hexlify(hash_obj).decode()

    # Create user
    registry.create_user(username, hash_hex, salt_hex, role, created_by=context.username)

    return {
        "success": True,
        "username": username,
    }


async def _update_user_role(
    context: MCPContext,
    username: str,
    role: str,
    **kwargs
) -> dict[str, Any]:
    """Update a user's role.

    Admin only.
    """
    context.require_permission("change_user_role")

    # Validate inputs
    if not username or not role:
        raise ValueError("Username and role required")

    if role not in ["admin", "deployer", "viewer"]:
        raise ValueError(f"Invalid role: {role!r}")

    # Check if user exists
    user = registry.get_user(username)
    if not user:
        raise ValueError(f"User {username!r} not found")

    # Update role
    registry.update_user_role(username, role)

    return {
        "success": True,
        "username": username,
        "new_role": role,
    }


async def _delete_user(context: MCPContext, username: str, **kwargs) -> dict[str, Any]:
    """Delete a user.

    Admin only. Cannot delete yourself.
    """
    context.require_permission("delete_user")

    # Validate inputs
    if not username:
        raise ValueError("Username required")

    # Check if user exists
    user = registry.get_user(username)
    if not user:
        raise ValueError(f"User {username!r} not found")

    # Cannot delete yourself
    if username == context.username:
        raise ValueError("Cannot delete yourself")

    # Delete user
    registry.delete_user(username)

    return {
        "success": True,
        "username": username,
    }


def register_users_tools() -> None:
    """Register user management tools."""
    register_tool("devps.users.list", _list_users)
    register_tool("devps.users.create", _create_user)
    register_tool("devps.users.update-role", _update_user_role)
    register_tool("devps.users.delete", _delete_user)
