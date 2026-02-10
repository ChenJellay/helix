"""GitHub webhook handler API routes."""

from __future__ import annotations

import hashlib
import hmac
import logging

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

from helix.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


def _verify_github_signature(payload: bytes, signature: str | None) -> bool:
    """Verify the GitHub webhook HMAC-SHA256 signature."""
    if not settings.github_webhook_secret or settings.helix_env == "development":
        return True

    if not signature:
        return False

    expected = hmac.new(
        settings.github_webhook_secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(f"sha256={expected}", signature)


def _verify_api_key(api_key: str | None) -> bool:
    """Verify the Helix API key (used by the GitHub Action path)."""
    if not api_key:
        return False
    return hmac.compare_digest(api_key, settings.helix_api_key)


async def _process_pr_webhook(repo_name: str, pr_number: int) -> None:
    """Background task: run scope check on the PR."""
    from helix.db.session import async_session_factory
    from helix.agents.scope_checker import ScopeCheckerAgent

    async with async_session_factory() as session:
        try:
            agent = ScopeCheckerAgent()
            await agent.check_pr(
                repo_name=repo_name,
                pr_number=pr_number,
                session=session,
            )
            await session.commit()
        except Exception:
            logger.exception("Scope check failed for %s#%d", repo_name, pr_number)
            await session.rollback()


@router.post("/webhooks/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str | None = Header(None),
    x_github_event: str | None = Header(None),
    x_api_key: str | None = Header(None),
):
    """Receive GitHub webhook events.

    Authenticates via either:
      1. GitHub HMAC signature (``X-Hub-Signature-256``) — direct webhook path
      2. Helix API key (``X-API-Key``) — GitHub Action path

    Handles pull_request events to trigger scope-creep checks.
    """
    payload = await request.body()

    # Authenticate: accept GitHub HMAC signature OR Helix API key
    sig_ok = _verify_github_signature(payload, x_hub_signature_256)
    key_ok = _verify_api_key(x_api_key)

    if not sig_ok and not key_ok:
        raise HTTPException(status_code=401, detail="Invalid webhook signature or API key")

    data = await request.json()

    # Only handle PR events
    if x_github_event != "pull_request":
        return {"status": "ignored", "event": x_github_event}

    action = data.get("action", "")
    if action not in ("opened", "synchronize", "reopened"):
        return {"status": "ignored", "action": action}

    pr = data.get("pull_request", {})
    repo = data.get("repository", {})
    repo_name = repo.get("full_name", "")
    pr_number = data.get("number", 0)

    if not repo_name or not pr_number:
        raise HTTPException(status_code=400, detail="Missing repo or PR info")

    logger.info(
        "Received PR webhook: %s#%d (%s) - %s",
        repo_name,
        pr_number,
        action,
        pr.get("title", ""),
    )

    # Trigger scope check in background
    background_tasks.add_task(_process_pr_webhook, repo_name, pr_number)

    return {
        "status": "processing",
        "repo": repo_name,
        "pr_number": pr_number,
        "action": action,
    }
