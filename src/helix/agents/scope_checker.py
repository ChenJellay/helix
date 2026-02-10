"""Scope Checker Agent - Stage 2: Execution.

Compares PR diffs against approved design documents to detect scope creep
and architecture violations.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from helix.agents.base import BaseAgent
from helix.integrations.github import GitHubClient
from helix.models.db import Project, ScopeCheckResult
from helix.rag.retriever import retrieve_design_doc, retrieve_repo_context

logger = logging.getLogger(__name__)


class ScopeCheckerAgent(BaseAgent):
    """Checks PRs for scope creep against approved design documents."""

    agent_name = "scope_checker"
    prompt_template = "scope_check.j2"

    def __init__(self, github_client: GitHubClient | None = None, **kwargs):
        super().__init__(**kwargs)
        self.github = github_client or GitHubClient()

    async def check_pr(
        self,
        repo_name: str,
        pr_number: int,
        session: AsyncSession,
    ) -> dict[str, Any]:
        """Run scope check on a pull request.

        Args:
            repo_name: Full repo name (owner/repo).
            pr_number: PR number.
            session: Active database session.

        Returns:
            Scope check results.
        """
        # 1. Find the project by repo URL
        result = await session.execute(
            select(Project).where(Project.github_repo.contains(repo_name))
        )
        project = result.scalar_one_or_none()
        if not project:
            logger.warning("No project found for repo %s", repo_name)
            return {"error": f"No project linked to repo {repo_name}"}

        project_id = str(project.id)

        # 2. Fetch the PR details and diff
        pr_info = await self.github.get_pr(repo_name, pr_number)
        diff = await self.github.get_pr_diff(repo_name, pr_number)

        # 3. Retrieve the design document from RAG
        design_doc = await retrieve_design_doc(project_id)
        if not design_doc:
            design_doc = "(No design document found for this project)"

        # 4. Get repo map context
        repo_map = await retrieve_repo_context(project.github_repo or repo_name)

        # 5. Budget-aware prompt rendering
        budget = self.create_budget()
        budget.reserve("template_chrome", 500)  # instructions + JSON schema
        budget.reserve("pr_meta", 200)           # title, description, etc.

        # Allocate remaining budget: 40% design doc, 10% repo map, 50% diff
        remaining = budget.remaining()
        design_fitted = budget.fit("design_doc", design_doc, max_tokens=int(remaining * 0.4))
        repo_map_fitted = budget.fit("repo_map", repo_map or "", max_tokens=int(remaining * 0.1))
        diff_fitted = budget.fit("diff", diff, max_tokens=int(remaining * 0.5))

        prompt = self.render_prompt(
            design_doc_content=design_fitted,
            repo_map=repo_map_fitted,
            pr_number=pr_number,
            repo_name=repo_name,
            pr_title=pr_info.get("title", ""),
            pr_description=pr_info.get("body", ""),
            diff_content=diff_fitted,
        )
        budget.log_summary(self.agent_name)

        result_data = await self.call_llm_structured(prompt)

        # 6. Store the scope check result
        check_result = ScopeCheckResult(
            project_id=project.id,
            pr_number=pr_number,
            repo_name=repo_name,
            alignment_score=result_data.get("alignment_score", 1.0),
            violations=result_data.get("violations", []),
            summary=result_data.get("summary", ""),
            requires_tpm_approval="yes" if result_data.get("requires_tpm_approval") else "no",
        )
        session.add(check_result)
        await session.flush()

        # 7. Post comment on PR if violations found
        violations = result_data.get("violations", [])
        if violations:
            comment = self._format_pr_comment(result_data)
            await self.github.post_pr_comment(repo_name, pr_number, comment)

        logger.info(
            "Scope check complete for %s#%d: score=%.2f, violations=%d",
            repo_name,
            pr_number,
            check_result.alignment_score,
            len(violations),
        )

        return {
            "check_id": str(check_result.id),
            "alignment_score": check_result.alignment_score,
            "violations": violations,
            "summary": check_result.summary,
            "requires_tpm_approval": check_result.requires_tpm_approval,
        }

    @staticmethod
    def _format_pr_comment(result_data: dict) -> str:
        """Format the scope check results as a GitHub PR comment."""
        lines = [
            "## Helix Scope Check Report",
            "",
            f"**Alignment Score:** {result_data.get('alignment_score', 'N/A')}",
            "",
        ]

        violations = result_data.get("violations", [])
        if violations:
            lines.append("### Violations Found")
            lines.append("")
            for v in violations:
                severity_icon = {
                    "critical": "🔴",
                    "warning": "🟡",
                    "info": "🔵",
                }.get(v.get("severity", ""), "⚪")
                lines.append(
                    f"- {severity_icon} **{v.get('violation_type', 'Unknown')}** "
                    f"in `{v.get('file', 'N/A')}`: {v.get('description', '')}"
                )
                if v.get("recommendation"):
                    lines.append(f"  - **Recommendation:** {v['recommendation']}")
            lines.append("")

        if result_data.get("requires_tpm_approval"):
            lines.append("⚠️ **TPM approval is required before merging this PR.**")
            lines.append("")

        lines.append(f"**Summary:** {result_data.get('summary', 'No summary available.')}")
        lines.append("")
        lines.append("---")
        lines.append("*Generated by Helix TPM Guardrails*")

        return "\n".join(lines)
