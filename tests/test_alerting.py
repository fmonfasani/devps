"""Tests for health check alerting."""

import os
from unittest.mock import MagicMock, patch

import pytest

from devps_agent import alerting


class TestSlackAlert:
    def test_slack_alert_no_webhook(self) -> None:
        """Test: Slack alert returns False if webhook not configured"""
        # Make sure DEVPS_SLACK_WEBHOOK_URL is not set
        with patch.dict(os.environ, {}, clear=True):
            result = alerting.send_slack_alert("test-app", "test message")
            assert result is False

    def test_slack_alert_success(self) -> None:
        """Test: Slack alert sends successfully"""
        with patch("devps_agent.alerting.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.__enter__.return_value = mock_response

            with patch.dict(os.environ, {"DEVPS_SLACK_WEBHOOK_URL": "http://example.com/hook"}):
                mock_urlopen.return_value = mock_response
                result = alerting.send_slack_alert("test-app", "test message")
                assert result is True

    def test_slack_alert_failure(self) -> None:
        """Test: Slack alert raises on request failure"""
        with patch("devps_agent.alerting.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = Exception("Connection error")

            with patch.dict(os.environ, {"DEVPS_SLACK_WEBHOOK_URL": "http://example.com/hook"}):
                with pytest.raises(alerting.AlertError):
                    alerting.send_slack_alert("test-app", "test message")


class TestEmailAlert:
    def test_email_alert_no_config(self) -> None:
        """Test: Email alert returns False if not configured"""
        with patch.dict(os.environ, {}, clear=True):
            result = alerting.send_email_alert("test-app", "test message")
            assert result is False

    def test_email_alert_success(self) -> None:
        """Test: Email alert sends successfully"""
        with patch("devps_agent.alerting.smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server

            env_vars = {
                "DEVPS_ALERT_EMAIL_TO": "admin@example.com",
                "DEVPS_ALERT_EMAIL_FROM": "alerts@devps.local",
                "DEVPS_ALERT_SMTP_HOST": "smtp.example.com",
                "DEVPS_ALERT_SMTP_PORT": "587",
            }

            with patch.dict(os.environ, env_vars):
                result = alerting.send_email_alert("test-app", "test message")
                assert result is True


class TestSendAlert:
    def test_send_alert_all_configured(self) -> None:
        """Test: send_alert returns results for both channels"""
        with patch("devps_agent.alerting.send_slack_alert") as mock_slack:
            with patch("devps_agent.alerting.send_email_alert") as mock_email:
                mock_slack.return_value = True
                mock_email.return_value = True

                results = alerting.send_alert("test-app", "test message")

                assert results["slack"] is True
                assert results["email"] is True

    def test_send_alert_partial_failure(self) -> None:
        """Test: send_alert continues if one channel fails"""
        with patch("devps_agent.alerting.send_slack_alert") as mock_slack:
            with patch("devps_agent.alerting.send_email_alert") as mock_email:
                mock_slack.side_effect = alerting.AlertError("Slack failed")
                mock_email.return_value = True

                results = alerting.send_alert("test-app", "test message")

                assert results["slack"] is False
                assert results["email"] is True
