"""Workspace discovery API routes — repo listing and branch enumeration."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from helix.api.deps import verify_api_key
from helix.integrations.local_git import LocalGitClient
from helix.integrations.path_resolver import repo_path_resolver

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/workspace/repos")
async def list_workspace_repos(
    _: str = Depends(verify_api_key),
):
    """Scan HELIX_WORKSPACE for git repositories (directories containing .git).

    Returns a list of ``{ name, path }`` dicts where *path* is the
    workspace-relative POSIX path suitable for storing in ``repo_path``.
    """
    workspace = repo_path_resolver.workspace

    if not workspace.is_dir():
        raise HTTPException(
            status_code=500,
            detail=(
                f"HELIX_WORKSPACE ({workspace}) does not exist or is not a "
                f"directory. Update your .env file."
            ),
        )

    repos: list[dict[str, str]] = []

    try:
        children = sorted(workspace.iterdir())
    except PermissionError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Cannot read workspace directory: {exc}",
        ) from exc

    for child in children:
        try:
            if not child.is_dir():
                continue
            if not (child / ".git").exists():
                continue
            rel = child.relative_to(workspace).as_posix()
            repos.append({"name": child.name, "path": rel})
        except (PermissionError, OSError):
            # Skip directories we can't read (e.g. .Trash on macOS in Docker)
            logger.debug("Skipping inaccessible path: %s", child)
            continue

    return {"workspace": str(workspace), "repos": repos}


@router.get("/workspace/repos/{repo_path:path}/branches")
async def list_repo_branches(
    repo_path: str,
    _: str = Depends(verify_api_key),
):
    """List local branches for a repository inside the workspace.

    *repo_path* is the workspace-relative path (e.g. ``"payments-service"``).

    Returns the list of branch names, the currently checked-out branch,
    and the detected default branch.
    """
    try:
        abs_path = repo_path_resolver.resolve(repo_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    git = LocalGitClient(abs_path)

    try:
        raw = await git._run("branch", "--format=%(refname:short)")
        branches = [b.strip() for b in raw.strip().splitlines() if b.strip()]
        current = await git.current_branch()
        default = await git.default_branch()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "repo_path": repo_path,
        "branches": branches,
        "current_branch": current,
        "default_branch": default,
    }
