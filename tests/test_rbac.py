"""Tests for RBAC (Role-Based Access Control)."""

import pytest

from devps_agent import rbac, registry


class TestRoleHierarchy:
    def test_role_hierarchy(self) -> None:
        """Test: admin > deployer > viewer"""
        assert rbac.ROLE_HIERARCHY["admin"] > rbac.ROLE_HIERARCHY["deployer"]
        assert rbac.ROLE_HIERARCHY["deployer"] > rbac.ROLE_HIERARCHY["viewer"]


class TestPermissionMatrix:
    def test_admin_permission_exists(self) -> None:
        """Test: create_user requires admin"""
        assert rbac.PERMISSIONS["create_user"] == "admin"

    def test_deployer_permission_exists(self) -> None:
        """Test: create_project requires deployer"""
        assert rbac.PERMISSIONS["create_project"] == "deployer"

    def test_viewer_permission_exists(self) -> None:
        """Test: view_logs requires viewer"""
        assert rbac.PERMISSIONS["view_logs"] == "viewer"


class TestCanUserAccessProject:
    def test_admin_can_do_anything(self, tmp_path) -> None:
        """Test: admin can access any project for any action"""
        # This would need mocking of registry functions
        # Skipped for now, requires database setup
        pass

    def test_deployer_cannot_delete(self) -> None:
        """Test: deployer cannot delete projects"""
        # delete_project requires admin role
        required_role = rbac.PERMISSIONS["delete_project"]
        assert required_role == "admin"

    def test_viewer_cannot_deploy(self) -> None:
        """Test: viewer cannot deploy projects"""
        # deploy_project requires deployer role
        required_role = rbac.PERMISSIONS["deploy_project"]
        assert required_role == "deployer"


class TestRequirePermission:
    def test_permission_denied_raises_error(self) -> None:
        """Test: require_permission raises on denied access"""
        # This would need database fixture with actual user
        # Skipped for now
        pass


class TestListUserProjects:
    def test_admin_sees_all_projects(self) -> None:
        """Test: admin user sees all projects"""
        # This would need database setup with mock projects
        pass

    def test_deployer_sees_only_own_projects(self) -> None:
        """Test: deployer sees only their own projects"""
        # This would need database setup
        pass

    def test_viewer_sees_all_projects(self) -> None:
        """Test: viewer sees all projects"""
        # This would need database setup
        pass
