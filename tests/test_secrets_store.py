"""Tests for secrets_store module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from devps_agent.secrets_store import write_env_file


class TestWriteEnvFile:
    @patch("devps_agent.secrets_store.Path")
    def test_write_env_file(self, mock_path_class: MagicMock, tmp_path: Path) -> None:
        mock_secrets_dir = MagicMock()
        mock_env_file = MagicMock()

        mock_path_class.return_value = mock_secrets_dir
        mock_secrets_dir.__truediv__ = lambda self, x: mock_env_file

        with patch("builtins.open", create=True) as mock_open:
            mock_file = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_file

            result = write_env_file("test-project", {"KEY1": "value1", "KEY2": "value2"})

            # Verify secrets dir was created
            mock_secrets_dir.mkdir.assert_called_once_with(parents=True, exist_ok=True)

            # Verify file was opened for writing
            mock_open.assert_called_once_with(mock_env_file, "w")

            # Verify chmod was called
            mock_env_file.chmod.assert_called_once_with(0o600)

    def test_write_env_file_integration(self, tmp_path: Path) -> None:
        with patch("devps_agent.secrets_store.Path") as mock_path_class:
            mock_secrets_dir = tmp_path / "secrets"
            mock_secrets_dir.mkdir(exist_ok=True)

            mock_path_class.return_value = mock_secrets_dir

            # Mock __truediv__ to return a Path object
            def mock_truediv(self, name):
                return mock_secrets_dir / name

            mock_path_class.return_value.__truediv__ = mock_truediv

            result = write_env_file(
                "test-project", {"DATABASE_URL": "postgres://localhost", "SECRET": "abc123"}
            )

            expected_path = str(mock_secrets_dir / "test-project.env")
            assert result == expected_path

    def test_write_env_file_real(self, tmp_path: Path) -> None:
        """Real test writing to temporary directory."""
        with patch("devps_agent.secrets_store.Path") as mock_path_class:
            secrets_dir = tmp_path / "secrets"
            mock_path_class.return_value = secrets_dir

            # Make __truediv__ return actual Path objects
            original_truediv = Path.__truediv__

            def custom_truediv(self, other):
                if self == secrets_dir or str(self).startswith(str(tmp_path)):
                    return secrets_dir / other
                return original_truediv(self, other)

            with patch.object(Path, "__truediv__", custom_truediv):
                secrets_dir.mkdir(parents=True, exist_ok=True)

                result = write_env_file(
                    "myproject",
                    {"DB_URL": "postgres://localhost/db", "API_KEY": "secret123"},
                )

                env_file = secrets_dir / "myproject.env"
                assert env_file.exists()

                content = env_file.read_text()
                assert "DB_URL=postgres://localhost/db" in content
                assert "API_KEY=secret123" in content
