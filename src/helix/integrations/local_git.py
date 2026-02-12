"""Local git client — replaces GitHubClient with local git CLI operations.

All methods operate against a resolved on-disk repository path.  Heavy
operations (``git diff``, ``git log``) are executed asynchronously via
``asyncio.create_subprocess_exec`` so the event loop is never blocked.

Usage::

    from helix.integrations.local_git import LocalGitClient

    git = LocalGitClient("payments-service")   # relative to HELIX_WORKSPACE
    diff = await git.diff("main", "feature/fraud-detection")
    log  = await git.log("main", "feature/fraud-detection")
    tree = await git.ls_tree()
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from helix.integrations.path_resolver import repo_path_resolver

logger = logging.getLogger(__name__)

# Timeout for any single git subprocess (seconds).
_GIT_TIMEOUT = 30


class LocalGitClient:
    """Async wrapper around the git CLI for a single local repository.

    Args:
        repo_path: Path to the repository — either a workspace-relative
                   string (e.g. ``"payments-service"``) or an already-
                   resolved :class:`~pathlib.Path`.
    """

    def __init__(self, repo_path: str | Path) -> None:
        if isinstance(repo_path, Path):
            self._repo_dir = repo_path
        else:
            self._repo_dir = repo_path_resolver.resolve(repo_path)

    # ── Public API ────────────────────────────────────────────────────

    async def diff(self, base: str, head: str) -> str:
        """Return the unified diff between two refs.

        Equivalent to ``git diff base..head``.
        """
        return await self._run("diff", f"{base}..{head}")

    async def log(
        self,
        base: str,
        head: str,
        *,
        format: str = "%H%n%s%n%b%n---",
        max_count: int = 50,
    ) -> str:
        """Return commit log between two refs.

        Equivalent to ``git log --format=<format> base..head``.
        """
        return await self._run(
            "log",
            f"--format={format}",
            f"--max-count={max_count}",
            f"{base}..{head}",
        )

    async def branch_summary(self, base: str, head: str) -> dict[str, Any]:
        """Build a PR-like summary dict from branch comparison.

        Returns a dict with ``title`` (first commit subject),
        ``body`` (all commit messages concatenated), and
        ``commit_count``.
        """
        raw = await self._run(
            "log",
            "--format=%s",
            f"{base}..{head}",
        )
        subjects = [s.strip() for s in raw.strip().splitlines() if s.strip()]

        title = subjects[0] if subjects else "(no commits)"
        body = "\n".join(subjects)

        return {
            "title": title,
            "body": body,
            "commit_count": len(subjects),
        }

    async def ls_tree(self, ref: str = "HEAD") -> list[str]:
        """Return a list of tracked file paths.

        Equivalent to ``git ls-tree -r --name-only <ref>``.
        """
        raw = await self._run("ls-tree", "-r", "--name-only", ref)
        return [line for line in raw.splitlines() if line.strip()]

    async def file_content(self, path: str, ref: str = "HEAD") -> str:
        """Return the content of a single file at the given ref.

        Equivalent to ``git show <ref>:<path>``.
        """
        return await self._run("show", f"{ref}:{path}")

    async def current_branch(self) -> str:
        """Return the name of the currently checked-out branch."""
        return (await self._run("rev-parse", "--abbrev-ref", "HEAD")).strip()

    async def default_branch(self) -> str:
        """Guess the default branch (``main`` or ``master``)."""
        branches = (await self._run("branch", "--list", "main", "master")).strip()
        for candidate in ("main", "master"):
            if candidate in branches:
                return candidate
        # Fallback: first branch in list
        all_branches = (await self._run("branch", "--format=%(refname:short)")).strip()
        return all_branches.splitlines()[0] if all_branches else "main"

    # ── Internals ─────────────────────────────────────────────────────

    async def _run(self, *args: str) -> str:
        """Execute ``git <args>`` inside the repo directory and return stdout."""
        cmd = ["git", "-C", str(self._repo_dir), *args]
        logger.debug("Running: %s", " ".join(cmd))

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=_GIT_TIMEOUT
            )
        except asyncio.TimeoutError:
            proc.kill()
            raise RuntimeError(
                f"git command timed out after {_GIT_TIMEOUT}s: {' '.join(cmd)}"
            ) from None

        if proc.returncode != 0:
            err = stderr.decode(errors="replace").strip()
            raise RuntimeError(
                f"git command failed (exit {proc.returncode}): {' '.join(cmd)}\n{err}"
            )

        return stdout.decode(errors="replace")
