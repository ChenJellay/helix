"""GitHub integration client for PR operations."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from helix.config import settings

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"


class GitHubClient:
    """Client for interacting with the GitHub REST API.

    Used by the Scope Checker agent to fetch PR details and post comments.
    """

    def __init__(self, token: str | None = None):
        self.token = token or settings.github_token
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Helix-TPM-Bot",
        }
        if self.token:
            self.headers["Authorization"] = f"token {self.token}"

    async def get_pr(self, repo: str, pr_number: int) -> dict[str, Any]:
        """Fetch pull request details.

        Args:
            repo: Full repo name (owner/repo).
            pr_number: PR number.

        Returns:
            PR data dict with title, body, head, base, etc.
        """
        url = f"{GITHUB_API_BASE}/repos/{repo}/pulls/{pr_number}"
        async with httpx.AsyncClient(headers=self.headers, timeout=30) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()

    async def get_pr_diff(self, repo: str, pr_number: int) -> str:
        """Fetch the diff content for a pull request.

        Args:
            repo: Full repo name (owner/repo).
            pr_number: PR number.

        Returns:
            The raw diff text.
        """
        url = f"{GITHUB_API_BASE}/repos/{repo}/pulls/{pr_number}"
        headers = {**self.headers, "Accept": "application/vnd.github.v3.diff"}
        async with httpx.AsyncClient(headers=headers, timeout=30) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text

    async def post_pr_comment(self, repo: str, pr_number: int, body: str) -> dict[str, Any]:
        """Post a comment on a pull request.

        Args:
            repo: Full repo name (owner/repo).
            pr_number: PR number.
            body: Comment body (markdown).

        Returns:
            Created comment data.
        """
        url = f"{GITHUB_API_BASE}/repos/{repo}/issues/{pr_number}/comments"
        async with httpx.AsyncClient(headers=self.headers, timeout=30) as client:
            response = await client.post(url, json={"body": body})
            response.raise_for_status()
            logger.info("Posted comment on %s#%d", repo, pr_number)
            return response.json()

    async def get_repo_tree(self, repo: str, branch: str = "main") -> list[dict[str, Any]]:
        """Fetch the file tree of a repository.

        Args:
            repo: Full repo name (owner/repo).
            branch: Branch name to fetch the tree from.

        Returns:
            List of file entries with path, type, size.
        """
        url = f"{GITHUB_API_BASE}/repos/{repo}/git/trees/{branch}?recursive=1"
        async with httpx.AsyncClient(headers=self.headers, timeout=30) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            return data.get("tree", [])

    async def get_file_content(self, repo: str, path: str, branch: str = "main") -> str:
        """Fetch a single file's content from a repository.

        Args:
            repo: Full repo name (owner/repo).
            path: File path within the repo.
            branch: Branch to read from.

        Returns:
            The file content as a string.
        """
        url = f"{GITHUB_API_BASE}/repos/{repo}/contents/{path}?ref={branch}"
        headers = {**self.headers, "Accept": "application/vnd.github.v3.raw"}
        async with httpx.AsyncClient(headers=headers, timeout=30) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text
