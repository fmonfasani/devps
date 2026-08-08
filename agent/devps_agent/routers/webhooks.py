"""GitHub webhook endpoints for automatic deployments."""

from fastapi import APIRouter, HTTPException, Request

from .. import webhooks as webhook_handler

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/github/{project_name}")
async def github_webhook(project_name: str, request: Request) -> dict:
    """GitHub webhook endpoint for automatic deployments.

    Receives push events from GitHub, validates signature, and triggers
    deployment if the pushed branch matches the project's configured branch.

    **Setup**:
    1. In GitHub repo → Settings → Webhooks → Add webhook
    2. Payload URL: `https://devps.webshooks.com/webhooks/github/{project_name}`
    3. Content type: `application/json`
    4. Secret: (same as DEVPS_WEBHOOK_SECRET)
    5. Events: Push events
    6. Active: ✅

    **Example payload**:
    ```json
    {
      "ref": "refs/heads/main",
      "before": "abc123...",
      "after": "def456...",
      "repository": {
        "clone_url": "https://github.com/user/repo.git",
        "name": "repo"
      },
      "commits": [...]
    }
    ```

    **Response**:
    - `status: deployed` — deployment triggered
    - `status: skipped` — branch not configured for auto-deploy
    - `status: error` — validation or deployment failed (HTTP 400)
    """
    # Get signature from GitHub header
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not signature:
        raise HTTPException(status_code=400, detail="missing X-Hub-Signature-256 header")

    # Get raw body for signature validation
    body = await request.body()

    # Parse JSON
    try:
        import json

        payload = json.loads(body)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"invalid JSON: {e}") from e

    # Handle webhook
    try:
        result = webhook_handler.handle_webhook(project_name, payload, signature)
        return result
    except webhook_handler.WebhookError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
