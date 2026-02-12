"""Local scope-check API route (local mode)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from helix.api.deps import get_db, verify_api_key
from helix.integrations.local_git import LocalGitClient
from helix.integrations.path_resolver import repo_path_resolver
from helix.models.schemas import LocalCheckRequest

logger = logging.getLogger(__name__)

router = APIRouter()


async def _run_local_scope_check(
    repo_path: str,
    base_branch: str,
    head_branch: str,
) -> None:
    """Background task: run the scope checker against local branches."""
    from helix.db.session import async_session_factory
    from helix.agents.scope_checker import ScopeCheckerAgent

    async with async_session_factory() as session:
        try:
            agent = ScopeCheckerAgent()
            await agent.check_branch(
                repo_path=repo_path,
                base_branch=base_branch,
                head_branch=head_branch,
                session=session,
            )
            await session.commit()
        except Exception:
            logger.exception(
                "Local scope check failed for %s (%s..%s)",
                repo_path,
                base_branch,
                head_branch,
            )
            await session.rollback()


@router.post("/check-local")
async def check_local(
    data: LocalCheckRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """Trigger a scope check on a local git repository.

    Accepts a repo path (absolute, ``~/``-prefixed, or relative to
    ``HELIX_WORKSPACE``), a base branch, and an optional head branch
    (defaults to the currently checked-out branch).
    """
    # Normalise to workspace-relative
    try:
        relative = repo_path_resolver.to_relative(data.repo_path)
    except ValueError:
        # Might already be relative — try resolving it directly
        relative = data.repo_path

    # Validate the repo exists
    try:
        abs_path = repo_path_resolver.resolve(relative)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Resolve head branch if not provided
    head_branch = data.head_branch
    if not head_branch:
        git = LocalGitClient(abs_path)
        head_branch = await git.current_branch()

    if head_branch == data.base_branch:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Head branch ({head_branch}) is the same as base branch "
                f"({data.base_branch}).  Checkout a feature branch first."
            ),
        )

    logger.info(
        "Queuing local scope check: %s (%s..%s)",
        relative,
        data.base_branch,
        head_branch,
    )

    background_tasks.add_task(
        _run_local_scope_check,
        relative,
        data.base_branch,
        head_branch,
    )

    return {
        "status": "processing",
        "repo_path": relative,
        "base_branch": data.base_branch,
        "head_branch": head_branch,
    }
