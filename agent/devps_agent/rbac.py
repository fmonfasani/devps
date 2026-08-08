"""Role-Based Access Control (RBAC) for devps.

Roles:
- admin: Full access (create users, projects, manage all projects)
- deployer: Can create projects and deploy (own projects)
- viewer: Read-only access to all projects
"""

from . import registry

# Role hierarchy: admin > deployer > viewer
ROLE_HIERARCHY = {"admin": 3, "deployer": 2, "viewer": 1}

# Permission matrix: action → required_role
PERMISSIONS = {
    # User management
    "create_user": "admin",
    "list_users": "admin",
    "delete_user": "admin",
    "change_user_role": "admin",
    # Project management
    "create_project": "deployer",
    "list_projects": "viewer",
    "view_project": "viewer",
    "deploy_project": "deployer",
    "redeploy_project": "deployer",
    "delete_project": "admin",
    "adopt_project": "admin",
    "edit_project": "deployer",  # Only own projects, unless admin
    # Viewing
    "view_logs": "viewer",
    "view_events": "viewer",
    "view_health": "viewer",
}


class RBACError(Exception):
    """RBAC authorization failed."""

    pass


def can_user_access_project(username: str, project_name: str, action: str) -> bool:
    """Check if user can perform action on project.

    Args:
        username: Username
        project_name: Project name
        action: Action to perform (e.g., 'deploy_project')

    Returns:
        True if user has permission, False otherwise

    Raises:
        RBACError: If user or project not found
    """
    user = registry.get_user(username)
    if not user:
        raise RBACError(f"User {username!r} not found")

    # Check if action requires permission
    required_role = PERMISSIONS.get(action)
    if not required_role:
        raise RBACError(f"Unknown action: {action!r}")

    # Admins can do everything
    if user["role"] == "admin":
        return True

    # Check role hierarchy
    user_level = ROLE_HIERARCHY.get(user["role"], 0)
    required_level = ROLE_HIERARCHY.get(required_role, 0)

    if user_level < required_level:
        return False

    # For project-specific actions, check ownership
    if action in ["edit_project", "redeploy_project", "deploy_project"]:
        project = registry.get_project(project_name)
        if not project:
            raise RBACError(f"Project {project_name!r} not found")

        # Deployer can only edit their own projects
        if user["role"] == "deployer" and project.get("owner") != username:
            return False

    return True


def require_permission(username: str, action: str, project_name: str | None = None) -> None:
    """Assert user has permission or raise RBACError.

    Args:
        username: Username
        action: Action to perform
        project_name: Project name (required for project-specific actions)

    Raises:
        RBACError: If permission denied
    """
    if project_name:
        if not can_user_access_project(username, project_name, action):
            raise RBACError(f"User {username!r} cannot {action} on {project_name!r}")
    else:
        user = registry.get_user(username)
        if not user:
            raise RBACError(f"User {username!r} not found")

        required_role = PERMISSIONS.get(action)
        if not required_role:
            raise RBACError(f"Unknown action: {action!r}")

        user_level = ROLE_HIERARCHY.get(user["role"], 0)
        required_level = ROLE_HIERARCHY.get(required_role, 0)

        if user_level < required_level:
            raise RBACError(f"User {username!r} cannot {action}")


def list_user_projects(username: str) -> list[dict]:
    """Get projects accessible to user.

    Admins see all projects.
    Deployers see only their own projects.
    Viewers see all projects (read-only).

    Args:
        username: Username

    Returns:
        List of project dicts

    Raises:
        RBACError: If user not found
    """
    user = registry.get_user(username)
    if not user:
        raise RBACError(f"User {username!r} not found")

    all_projects = registry.list_projects()

    if user["role"] == "admin" or user["role"] == "viewer":
        # Admins and viewers see all projects
        return all_projects

    # Deployers see only their own projects
    if user["role"] == "deployer":
        return [p for p in all_projects if p.get("owner") == username]

    return []
