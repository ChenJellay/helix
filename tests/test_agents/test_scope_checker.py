"""Tests for the Scope Checker agent."""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from helix.agents.scope_checker import ScopeCheckerAgent


class TestScopeCheckerAgent:
    """Tests for the Scope Checker agent."""

    def test_format_pr_comment_with_violations(self, sample_scope_check_response):
        """Test PR comment formatting with violations."""
        comment = ScopeCheckerAgent._format_pr_comment(sample_scope_check_response)

        assert "Helix Scope Check Report" in comment
        assert "scope_creep" in comment
        assert "TPM approval" in comment
        assert "Helix TPM Guardrails" in comment

    def test_format_pr_comment_no_violations(self):
        """Test PR comment formatting without violations."""
        data = {
            "alignment_score": 1.0,
            "violations": [],
            "summary": "All good!",
            "requires_tpm_approval": False,
        }
        comment = ScopeCheckerAgent._format_pr_comment(data)

        assert "Helix Scope Check Report" in comment
        assert "All good!" in comment
        assert "TPM approval" not in comment

    @pytest.mark.asyncio
    async def test_check_pr_with_violations(
        self, mock_llm, sample_scope_check_response
    ):
        """Test scope check that finds violations."""
        mock_llm.complete.return_value.content = json.dumps(sample_scope_check_response)
        mock_llm.embed.return_value = [[0.0] * 384]

        mock_github = AsyncMock()
        mock_github.get_pr.return_value = {"title": "Add feature", "body": "desc"}
        mock_github.get_pr_diff.return_value = "diff content here"
        mock_github.post_pr_comment.return_value = {}

        # Mock session
        mock_session = AsyncMock()
        mock_project = MagicMock()
        mock_project.id = uuid.uuid4()
        mock_project.github_repo = "owner/repo"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_project
        mock_session.execute.return_value = mock_result

        agent = ScopeCheckerAgent(github_client=mock_github, llm=mock_llm)

        with (
            patch(
                "helix.agents.scope_checker.retrieve_design_doc",
                new_callable=AsyncMock,
                return_value="Design doc content",
            ),
            patch(
                "helix.agents.scope_checker.retrieve_repo_context",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            result = await agent.check_pr(
                repo_name="owner/repo",
                pr_number=42,
                session=mock_session,
            )

        assert result["alignment_score"] == 0.6
        assert len(result["violations"]) == 1
        mock_github.post_pr_comment.assert_called_once()
