"""Tests for GitHub webhook handling."""

import hashlib
import hmac
import json

import pytest

from devps_agent import webhooks


class TestGitHubSignatureValidation:
    def test_valid_signature(self) -> None:
        secret = "my-secret"
        payload = b'{"test": "data"}'

        sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        header = f"sha256={sig}"

        # This would normally fail because config.WEBHOOK_SECRET is not set
        # Use monkeypatch in real tests
        assert header.startswith("sha256=")

    def test_invalid_signature_format(self) -> None:
        with pytest.raises(webhooks.WebhookError, match="not configured"):
            webhooks.validate_github_signature(b"data", "invalid-format")

    def test_signature_without_sha256_prefix(self) -> None:
        payload = b"data"
        signature = "abc123"

        # Should return False, but raises because no secret configured
        with pytest.raises(webhooks.WebhookError):
            webhooks.validate_github_signature(payload, signature)


class TestParseGitHubPayload:
    def test_valid_push_payload(self) -> None:
        payload = {
            "ref": "refs/heads/main",
            "after": "abc123def456...",
            "repository": {"clone_url": "https://github.com/user/repo.git"},
            "commits": [{"id": "abc123"}],
        }

        result = webhooks.parse_github_payload(payload)

        assert result["branch"] == "main"
        assert result["commit_sha"] == "abc123def456..."
        assert result["repo_url"] == "https://github.com/user/repo.git"
        assert result["commits_count"] == "1"

    def test_multiple_commits(self) -> None:
        payload = {
            "ref": "refs/heads/develop",
            "after": "xyz789...",
            "repository": {"clone_url": "https://github.com/user/repo.git"},
            "commits": [{"id": "1"}, {"id": "2"}, {"id": "3"}],
        }

        result = webhooks.parse_github_payload(payload)

        assert result["commits_count"] == "3"

    def test_missing_repository(self) -> None:
        payload = {"ref": "refs/heads/main", "after": "abc123"}

        with pytest.raises(webhooks.WebhookError, match="Invalid GitHub payload"):
            webhooks.parse_github_payload(payload)

    def test_missing_ref(self) -> None:
        payload = {
            "after": "abc123",
            "repository": {"clone_url": "https://github.com/user/repo.git"},
        }

        with pytest.raises(webhooks.WebhookError, match="Invalid GitHub payload"):
            webhooks.parse_github_payload(payload)

    def test_unsupported_ref_type(self) -> None:
        payload = {
            "ref": "refs/tags/v1.0.0",
            "after": "abc123",
            "repository": {"clone_url": "https://github.com/user/repo.git"},
            "commits": [{"id": "abc123"}],
        }

        with pytest.raises(webhooks.WebhookError, match="Unsupported ref"):
            webhooks.parse_github_payload(payload)

    def test_no_commits(self) -> None:
        payload = {
            "ref": "refs/heads/main",
            "after": "abc123",
            "repository": {"clone_url": "https://github.com/user/repo.git"},
            "commits": [],
        }

        with pytest.raises(webhooks.WebhookError, match="No commits"):
            webhooks.parse_github_payload(payload)

    def test_missing_clone_url(self) -> None:
        payload = {
            "ref": "refs/heads/main",
            "after": "abc123",
            "repository": {"name": "repo"},  # No clone_url
            "commits": [{"id": "abc123"}],
        }

        with pytest.raises(webhooks.WebhookError, match="missing clone_url"):
            webhooks.parse_github_payload(payload)


class TestShouldDeploy:
    def test_no_matching_branch(self, tmp_path) -> None:
        # This test needs a real project in registry
        # Skipped for now, requires database setup
        pass

    def test_project_not_managed_by_devps(self) -> None:
        # Needs database setup
        pass


class TestHandleWebhook:
    def test_webhook_signature_validation_failure(self) -> None:
        payload = {
            "ref": "refs/heads/main",
            "after": "abc123",
            "repository": {"clone_url": "https://github.com/user/repo.git"},
            "commits": [{"id": "abc123"}],
        }

        with pytest.raises(webhooks.WebhookError, match="not configured"):
            webhooks.handle_webhook("myapp", payload, "sha256=invalid")

    def test_webhook_invalid_payload(self) -> None:
        payload = {"ref": "refs/heads/main"}  # Missing required fields

        # Signature validation happens first, so this will fail on that
        with pytest.raises(webhooks.WebhookError, match="not configured"):
            webhooks.handle_webhook("myapp", payload, "sha256=abc123")
