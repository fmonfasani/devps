"""GitHub webhook handling for automatic deployments."""

import hashlib
import hmac
import json
from typing import Any

from . import config, registry
from .models import DeployRequest
from .routers.projects import deploy as deploy_project


class WebhookError(ValueError):
    """Webhook validation error."""

    pass


def validate_github_signature(payload_bytes: bytes, signature: str) -> bool:
    """Validate GitHub X-Hub-Signature-256 header.

    Args:
        payload_bytes: Raw request body bytes
        signature: X-Hub-Signature-256 header value (format: sha256=hex)

    Returns:
        True if signature is valid, False otherwise

    Raises:
        WebhookError: If webhook secret is not configured
    """
    if not config.WEBHOOK_SECRET:
        raise WebhookError("DEVPS_WEBHOOK_SECRET not configured")

    if not signature.startswith("sha256="):
        return False

    expected_sig = hmac.new(
        config.WEBHOOK_SECRET.encode(),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()

    provided_sig = signature[7:]  # Strip "sha256=" prefix
    return hmac.compare_digest(expected_sig, provided_sig)


def parse_github_payload(payload: dict[str, Any]) -> dict[str, str]:
    """Extract deployment info from GitHub push payload.

    Returns dict with:
        - repo_url: HTTPS git URL
        - branch: branch name (without refs/heads/)
        - commit_sha: full commit SHA
        - commits_count: number of commits in push

    Raises:
        WebhookError: If payload is invalid or missing required fields
    """
    # Validate basic structure
    if "repository" not in payload or "ref" not in payload:
        raise WebhookError("Invalid GitHub payload: missing repository or ref")

    repo = payload["repository"]
    if "clone_url" not in repo:
        raise WebhookError("Invalid repository: missing clone_url")

    # Extract branch name (refs/heads/main → main)
    ref = payload["ref"]
    if not ref.startswith("refs/heads/"):
        raise WebhookError(f"Unsupported ref: {ref} (only push to branches supported)")

    branch = ref[len("refs/heads/") :]

    # Get commit SHA
    commits = payload.get("commits", [])
    if not commits:
        raise WebhookError("No commits in push")

    commit_sha = payload.get("after")
    if not commit_sha:
        raise WebhookError("Missing commit SHA (after field)")

    return {
        "repo_url": repo["clone_url"],
        "branch": branch,
        "commit_sha": commit_sha,
        "commits_count": str(len(commits)),
    }


def should_deploy(project_name: str, pushed_branch: str) -> bool:
    """Check if deployment should be triggered.

    Deployment happens if:
    1. Project exists
    2. Project is managed by devps (not adopted)
    3. Pushed branch matches project's git_ref

    Args:
        project_name: devps project name
        pushed_branch: branch that was pushed to

    Returns:
        True if deployment should proceed
    """
    project = registry.get_project(project_name)
    if not project:
        return False

    if project["managed_by"] != "devps":
        return False

    # Project's tracked branch
    project_branch = project.get("git_ref", "main")
    return pushed_branch == project_branch


def trigger_deploy(
    project_name: str,
    repo_url: str,
    git_ref: str,
    domain: str | None = None,
) -> dict[str, Any]:
    """Trigger automatic deployment.

    Uses existing project configuration (services, primary_service, etc.)
    and redeploys from the specified git ref.

    Args:
        project_name: devps project name
        repo_url: Git repository URL
        git_ref: Branch/tag/commit to deploy
        domain: Optional domain (if provided, triggers cutover for migrations)

    Returns:
        Deployment result from deploy()

    Raises:
        WebhookError: If project not found or not managed by devps
    """
    project = registry.get_project(project_name)
    if not project:
        raise WebhookError(f"Project {project_name!r} not found")

    if project["managed_by"] != "devps":
        raise WebhookError(f"Project {project_name!r} not managed by devps")

    # Get service configuration from existing project
    ports_map = {p["service"]: p["container_port"] for p in project.get("ports", [])}
    if not ports_map:
        raise WebhookError(f"Project {project_name!r} has no services configured")

    # Primary service: use existing one or first available
    primary_service = project.get("primary_service")
    if not primary_service and ports_map:
        primary_service = next(iter(ports_map.keys()))

    # Deploy with existing configuration
    deploy_req = DeployRequest(
        repo_url=repo_url,
        git_ref=git_ref,
        compose_file=project.get("compose_file", "docker-compose.yml"),
        env_file=project.get("env_file"),
        domain=domain or project.get("domain"),
        services=ports_map,
        primary_service=primary_service,
    )

    result = deploy_project(project_name, deploy_req)
    registry.log_event(
        project_name,
        "webhook_deploy",
        f"auto-deploy from webhook, git_ref={git_ref}",
        success=True,
    )
    return result


def handle_webhook(project_name: str, payload: dict[str, Any], signature: str) -> dict[str, Any]:
    """Main webhook handler.

    Full flow:
    1. Validate GitHub signature
    2. Parse payload (extract branch, repo_url, commit_sha)
    3. Check if deployment should trigger
    4. Trigger deployment if conditions met

    Args:
        project_name: devps project name (from URL path)
        payload: Parsed JSON payload from GitHub
        signature: X-Hub-Signature-256 header

    Returns:
        Response dict with status and deployment info

    Raises:
        WebhookError: On any validation failure
    """
    # Validate signature
    payload_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    if not validate_github_signature(payload_bytes, signature):
        raise WebhookError("Invalid webhook signature")

    # Parse payload
    info = parse_github_payload(payload)

    # Check if deployment should happen
    if not should_deploy(project_name, info["branch"]):
        return {
            "status": "skipped",
            "reason": f"branch {info['branch']!r} not configured for auto-deploy",
            "project": project_name,
        }

    # Trigger deployment
    try:
        result = trigger_deploy(
            project_name,
            repo_url=info["repo_url"],
            git_ref=info["branch"],
        )
        return {
            "status": "deployed",
            "project": project_name,
            "branch": info["branch"],
            "commit": info["commit_sha"],
            "git_sha": result.get("git_sha"),
        }
    except Exception as e:
        registry.log_event(
            project_name,
            "webhook_deploy",
            f"webhook auto-deploy failed: {e}",
            success=False,
        )
        raise WebhookError(f"Deployment failed: {e}") from e
