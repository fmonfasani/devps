"""Tests for repo_analysis module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from devps_agent.repo_analysis import (
    classify_and_generate,
    parse_compose_services,
    parse_env_example,
)


class TestParseComposeServices:
    def test_parse_services_with_devps_port_convention(self, tmp_path: Path) -> None:
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text(
            """
services:
  web:
    image: nginx
    ports:
      - "127.0.0.1:${DEVPS_PORT_WEB:-3000}:3000"
  api:
    image: node
    ports:
      - "${DEVPS_PORT_API:-8000}:8080"
"""
        )

        result = parse_compose_services(compose_file)

        assert "web" in result
        assert result["web"]["container_port"] == 3000
        assert result["web"]["host_port_var"] == "WEB"
        assert result["web"]["needs_manual_edit"] is False

        assert "api" in result
        assert result["api"]["container_port"] == 8080
        assert result["api"]["host_port_var"] == "API"
        assert result["api"]["needs_manual_edit"] is False

    def test_parse_services_without_devps_convention(self, tmp_path: Path) -> None:
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text(
            """
services:
  web:
    image: nginx
    ports:
      - "127.0.0.1:3000:3000"
"""
        )

        result = parse_compose_services(compose_file)

        assert "web" in result
        assert result["web"]["container_port"] == 3000
        assert result["web"]["needs_manual_edit"] is True
        assert result["web"]["host_port_var"] is None

    def test_parse_services_no_ports(self, tmp_path: Path) -> None:
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text(
            """
services:
  worker:
    image: node
    # no ports exposed
"""
        )

        result = parse_compose_services(compose_file)
        assert "worker" not in result

    def test_parse_empty_compose_file(self, tmp_path: Path) -> None:
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("")

        result = parse_compose_services(compose_file)
        assert result == {}


class TestParseEnvExample:
    def test_parse_env_example(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env.example"
        env_file.write_text(
            """
DATABASE_URL=postgres://localhost/db
JWT_SECRET=
API_KEY=sk-xxx
# This is a comment
INTERNAL_TOKEN=
SOMETHING_ELSE=default_value
"""
        )

        result = parse_env_example(tmp_path)

        assert "DATABASE_URL" in result
        assert "JWT_SECRET" in result
        assert "API_KEY" in result
        assert "INTERNAL_TOKEN" in result
        assert "SOMETHING_ELSE" in result
        # Comments should not be included
        assert len(result) == 5

    def test_parse_env_example_missing_file(self, tmp_path: Path) -> None:
        result = parse_env_example(tmp_path)
        assert result == []

    def test_parse_env_example_empty_file(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env.example"
        env_file.write_text("")

        result = parse_env_example(tmp_path)
        assert result == []


class TestClassifyAndGenerate:
    def test_classify_generatable_variables(self) -> None:
        var_names = [
            "DATABASE_PASSWORD",
            "JWT_SECRET",
            "INTERNAL_AUTH_TOKEN",
            "API_KEY",
            "SESSION_SECRET",
        ]

        result = classify_and_generate(var_names)

        # Generatable ones should have values
        assert result["DATABASE_PASSWORD"]["generatable"] is True
        assert result["DATABASE_PASSWORD"]["value"] is not None
        assert len(result["DATABASE_PASSWORD"]["value"]) == 48  # hex(24) = 48 chars

        assert result["JWT_SECRET"]["generatable"] is True
        assert result["JWT_SECRET"]["value"] is not None

        assert result["INTERNAL_AUTH_TOKEN"]["generatable"] is True
        assert result["INTERNAL_AUTH_TOKEN"]["value"] is not None

        # Non-generatable
        assert result["API_KEY"]["generatable"] is False
        assert result["API_KEY"]["value"] is None

    def test_classify_encryption_keys(self) -> None:
        var_names = [
            "ENCRYPTION_KEY",
            "COOKIE_SECRET",
            "CSRF_SECRET",
            "SALT",
            "VERIFY_TOKEN",
            "AUTH_SECRET",
        ]

        result = classify_and_generate(var_names)

        for var_name in var_names:
            assert result[var_name]["generatable"] is True
            assert result[var_name]["value"] is not None

    def test_classify_internal_variables(self) -> None:
        var_names = [
            "INTERNAL_DEBUG_KEY",
            "INTERNAL_CACHE_SECRET",
            "PUBLIC_API_KEY",
        ]

        result = classify_and_generate(var_names)

        assert result["INTERNAL_DEBUG_KEY"]["generatable"] is True
        assert result["INTERNAL_CACHE_SECRET"]["generatable"] is True
        assert result["PUBLIC_API_KEY"]["generatable"] is False

    def test_generated_values_are_unique(self) -> None:
        var_names = ["DATABASE_PASSWORD", "SESSION_SECRET", "JWT_SECRET"]

        result = classify_and_generate(var_names)

        values = [result[v]["value"] for v in var_names]
        assert len(set(values)) == 3  # All unique
        assert all(v is not None for v in values)
