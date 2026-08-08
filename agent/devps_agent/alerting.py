"""Alert management for health check failures."""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from urllib.request import Request, urlopen

from . import config


class AlertError(Exception):
    """Alert delivery failed."""

    pass


def send_slack_alert(project_name: str, message: str) -> bool:
    """Send Slack notification.

    Requires DEVPS_SLACK_WEBHOOK_URL environment variable.

    Args:
        project_name: Project name
        message: Alert message

    Returns:
        True if sent successfully, False if webhook not configured
    """
    webhook_url = os.environ.get("DEVPS_SLACK_WEBHOOK_URL")
    if not webhook_url:
        return False

    import json

    payload = {
        "text": f"🚨 *{project_name}* health alert",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{project_name}* health alert:\n{message}",
                },
            }
        ],
    }

    try:
        req = Request(
            webhook_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urlopen(req, timeout=5) as response:
            return response.status == 200
    except Exception as e:
        raise AlertError(f"Slack alert failed: {e}") from e


def send_email_alert(project_name: str, message: str) -> bool:
    """Send email notification.

    Requires environment variables:
    - DEVPS_ALERT_EMAIL_TO: recipient email
    - DEVPS_ALERT_EMAIL_FROM: sender email
    - DEVPS_ALERT_SMTP_HOST: SMTP host
    - DEVPS_ALERT_SMTP_PORT: SMTP port (optional, default 587)

    Args:
        project_name: Project name
        message: Alert message

    Returns:
        True if sent successfully, False if email not configured
    """
    recipient = os.environ.get("DEVPS_ALERT_EMAIL_TO")
    sender = os.environ.get("DEVPS_ALERT_EMAIL_FROM")
    smtp_host = os.environ.get("DEVPS_ALERT_SMTP_HOST")
    smtp_port = int(os.environ.get("DEVPS_ALERT_SMTP_PORT", "587"))

    if not all([recipient, sender, smtp_host]):
        return False

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = f"devps alert: {project_name} health check failed"

    body = f"Project: {project_name}\n\n{message}"
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.send_message(msg)
        return True
    except Exception as e:
        raise AlertError(f"Email alert failed: {e}") from e


def send_alert(project_name: str, message: str) -> dict[str, bool]:
    """Send alerts via all configured channels.

    Args:
        project_name: Project name
        message: Alert message

    Returns:
        Dict with keys "slack", "email" indicating success for each
    """
    results = {"slack": False, "email": False}

    try:
        results["slack"] = send_slack_alert(project_name, message)
    except AlertError:
        pass

    try:
        results["email"] = send_email_alert(project_name, message)
    except AlertError:
        pass

    return results
