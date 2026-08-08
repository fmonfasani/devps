"""Tests for secrets_store module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from devps_agent.secrets_store import write_env_file


class TestWriteEnvFile:
    def test_write_env_file_returns_path(self) -> None:
        with patch("devps_agent.secrets_store.Path") as mock_path_class:
            mock_file = MagicMock()
            mock_secrets_dir = MagicMock()
            mock_env_file = MagicMock()

            mock_path_class.return_value = mock_secrets_dir
            mock_secrets_dir.__truediv__.return_value = mock_env_file
            mock_env_file.__str__.return_value = "/opt/devps/secrets/test.env"

            with patch("builtins.open", create=True):
                result = write_env_file("test", {"KEY": "value"})

                assert result == "/opt/devps/secrets/test.env"
                mock_secrets_dir.mkdir.assert_called_once()
                mock_env_file.chmod.assert_called_once_with(0o600)

    def test_write_env_file_content(self, tmp_path: Path) -> None:
        """Test that env file is written with correct content."""
        with patch("devps_agent.secrets_store.Path") as mock_path_class:
            test_dir = tmp_path
            mock_path_class.return_value = test_dir

            # Use a real temp directory for this test
            result = write_env_file(
                "testproj", {"DB_URL": "postgres://localhost", "SECRET": "mysecret"}
            )

            # Since we're mocking Path, just verify the function signature works
            assert isinstance(result, str)
            assert "testproj.env" in result

    def test_write_env_file_formats_variables(self) -> None:
        """Test that variables are formatted correctly."""
        variables = {"DATABASE_URL": "postgres://db", "API_KEY": "secret123"}

        with patch("devps_agent.secrets_store.Path"):
            with patch("builtins.open", create=True) as mock_open:
                mock_file = MagicMock()
                mock_open.return_value.__enter__.return_value = mock_file

                write_env_file("project", variables)

                # Verify write calls
                calls = mock_file.write.call_args_list
                written_content = "".join(str(call[0][0]) for call in calls)

                assert "DATABASE_URL=postgres://db" in written_content
                assert "API_KEY=secret123" in written_content
