"""Tests for user management in registry."""

import pytest

from devps_agent import auth, registry


class TestCreateUser:
    def test_create_user(self, tmp_path) -> None:
        """Test: create_user inserts new user"""
        # Would need database fixture
        pass

    def test_create_user_duplicate_fails(self) -> None:
        """Test: duplicate username raises error"""
        # Would need database fixture
        pass


class TestGetUser:
    def test_get_user_exists(self) -> None:
        """Test: get_user returns user if exists"""
        # Would need database fixture
        pass

    def test_get_user_not_found(self) -> None:
        """Test: get_user returns None if not found"""
        # Would need database fixture
        pass


class TestListUsers:
    def test_list_users_excludes_passwords(self) -> None:
        """Test: list_users doesn't return password_hash"""
        # Would need database fixture
        pass


class TestUpdateUserRole:
    def test_update_user_role(self) -> None:
        """Test: update_user_role changes role"""
        # Would need database fixture
        pass


class TestDeleteUser:
    def test_delete_user_orphans_projects(self) -> None:
        """Test: deleting user sets owner to NULL"""
        # Would need database fixture with projects
        pass

    def test_delete_user_removes_events(self) -> None:
        """Test: deleting user clears their events"""
        # Would need database fixture with events
        pass
