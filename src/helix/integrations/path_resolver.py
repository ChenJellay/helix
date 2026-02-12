"""Repo path resolver — normalises, validates, and resolves project paths.

All repo paths stored in the database are **relative** to the workspace root
(``settings.helix_workspace``).  At runtime they are resolved to absolute
``pathlib.Path`` objects via this utility.

Usage::

    from helix.integrations.path_resolver import repo_path_resolver

    abs_path = repo_path_resolver.resolve("payments-service")
    rel_path = repo_path_resolver.to_relative("/Users/me/projects/payments-service")
"""

from __future__ import annotations

import logging
from pathlib import Path

from helix.config import settings

logger = logging.getLogger(__name__)


class RepoPathResolver:
    """Converts between relative (stored) and absolute (runtime) repo paths.

    The single source of truth for the workspace root is
    ``settings.helix_workspace``.
    """

    # ── Resolution ────────────────────────────────────────────────────

    @property
    def workspace(self) -> Path:
        """Return the resolved workspace root as an absolute ``Path``."""
        return Path(settings.helix_workspace).expanduser().resolve()

    def resolve(self, relative_path: str) -> Path:
        """Convert a stored relative path to an absolute ``Path``.

        Args:
            relative_path: Path relative to ``HELIX_WORKSPACE``
                           (e.g. ``"payments-service"``).

        Returns:
            Absolute ``Path`` to the repository directory.

        Raises:
            ValueError: If the resolved path escapes the workspace or is
                        not a valid git repository.
        """
        resolved = (self.workspace / relative_path).resolve()
        self._validate(resolved)
        return resolved

    # ── Normalisation ─────────────────────────────────────────────────

    def to_relative(self, path: str) -> str:
        """Normalise an input path (absolute or relative) to a workspace-
        relative string suitable for storage in the database.

        Args:
            path: An absolute path, a ``~/``-prefixed path, or a plain
                  relative path.

        Returns:
            A POSIX-style relative path string
            (e.g. ``"payments-service"``).

        Raises:
            ValueError: If the path is outside the workspace.
        """
        p = Path(path).expanduser().resolve()

        try:
            rel = p.relative_to(self.workspace)
        except ValueError:
            raise ValueError(
                f"Path {p} is outside the workspace ({self.workspace}). "
                f"Move the repository under HELIX_WORKSPACE or update the "
                f"HELIX_WORKSPACE setting."
            ) from None

        # Guard against degenerate inputs that resolve to workspace itself
        rel_str = rel.as_posix()
        if rel_str == ".":
            raise ValueError(
                "Path resolves to the workspace root itself; "
                "expected a subdirectory."
            )

        return rel_str

    # ── Validation ────────────────────────────────────────────────────

    def _validate(self, absolute: Path) -> None:
        """Validate that *absolute* is inside the workspace and is a git repo.

        Raises:
            ValueError: On any validation failure.
        """
        # Must be inside the workspace (no ../ escape)
        try:
            absolute.relative_to(self.workspace)
        except ValueError:
            raise ValueError(
                f"Resolved path {absolute} escapes the workspace "
                f"({self.workspace})."
            ) from None

        if not absolute.is_dir():
            raise ValueError(f"Path does not exist or is not a directory: {absolute}")

        if not (absolute / ".git").exists():
            raise ValueError(
                f"Path {absolute} is not a git repository "
                f"(no .git directory found)."
            )

    def validate_workspace(self) -> None:
        """Check that the workspace root itself exists.

        Raises:
            ValueError: If ``HELIX_WORKSPACE`` does not point to a valid
                        directory.
        """
        ws = self.workspace
        if not ws.is_dir():
            raise ValueError(
                f"HELIX_WORKSPACE ({ws}) does not exist or is not a "
                f"directory.  Create it or update your .env."
            )


# Module-level singleton — import and use directly.
repo_path_resolver = RepoPathResolver()
