"""MCP execution context — carries authenticated user info and RBAC checks."""

from dataclasses import dataclass
from typing import Optional

from .. import rbac, registry


@dataclass
class MCPContext:
    """Context for MCP tool execution.

    Carries authenticated user info and provides RBAC enforcement.
    """
    username: Optional[str] = None
    user: Optional[dict] = None

    @staticmethod
    def anonymous() -> 'MCPContext':
        """Create anonymous context (no auth)."""
        return MCPContext(username=None, user=None)

    @staticmethod
    def from_username(username: str) -> 'MCPContext':
        """Create context from username.

        Args:
            username: Authenticated username

        Returns:
            MCPContext with user loaded from registry

        Raises:
            ValueError: If user not found
        """
        user = registry.get_user(username)
        if not user:
            raise ValueError(f"User {username!r} not found")
        return MCPContext(username=username, user=user)

    def is_authenticated(self) -> bool:
        """Check if context has authenticated user."""
        return self.username is not None and self.user is not None

    def require_permission(self, action: str, project_name: Optional[str] = None) -> None:
        """Assert user has permission or raise rbac.RBACError.

        Args:
            action: Action to check (e.g., "view_project")
            project_name: Project name (required for project-specific actions)

        Raises:
            rbac.RBACError: If permission denied or user not authenticated
        """
        if not self.is_authenticated():
            raise rbac.RBACError("Not authenticated")

        rbac.require_permission(self.username, action, project_name)
