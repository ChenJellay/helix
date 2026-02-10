"""Gap Analyzer Agent - Stage 4: Value Stewardship.

Monitors post-launch metrics against PRD promises and generates
gap analysis reports when targets are not met.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from helix.agents.base import BaseAgent
from helix.integrations.metrics import MetricsClient
from helix.models.db import Document, GapAnalysis, MetricTarget, Project

logger = logging.getLogger(__name__)


class GapAnalyzerAgent(BaseAgent):
    """Monitors post-launch metrics and generates gap analysis reports."""

    agent_name = "gap_analyzer"
    prompt_template = "gap_analysis.j2"

    def __init__(self, metrics_client: MetricsClient | None = None, **kwargs):
        super().__init__(**kwargs)
        self.metrics = metrics_client or MetricsClient()

    async def analyze_gaps(
        self,
        project_id: str,
        session: AsyncSession,
    ) -> dict[str, Any]:
        """Run gap analysis for a launched project.

        Args:
            project_id: UUID of the project.
            session: Active database session.

        Returns:
            Gap analysis results.
        """
        # 1. Fetch project
        result = await session.execute(
            select(Project).where(Project.id == project_id)
        )
        project = result.scalar_one_or_none()
        if not project:
            raise ValueError(f"Project {project_id} not found")

        # 2. Fetch metric targets
        targets_result = await session.execute(
            select(MetricTarget).where(MetricTarget.project_id == project_id)
        )
        metric_targets = targets_result.scalars().all()

        if not metric_targets:
            return {
                "status": "no_targets",
                "message": "No metric targets defined for this project.",
            }

        # 3. Fetch current metric values from monitoring
        for target in metric_targets:
            actual = await self.metrics.get_metric_value(
                project.github_repo or "", target.metric_name
            )
            if actual is not None:
                target.actual_value = str(actual)
                target.checked_at = datetime.now(timezone.utc)

        # 4. Fetch project documents for context
        docs_result = await session.execute(
            select(Document).where(Document.project_id == project_id)
        )
        documents = docs_result.scalars().all()

        # 5. Calculate days since launch
        days_since_launch = (datetime.now(timezone.utc) - project.created_at.replace(
            tzinfo=timezone.utc
        )).days if project.created_at else 0

        # 6. Render prompt and call LLM
        targets_for_prompt = []
        for t in metric_targets:
            gap = None
            try:
                target_num = float(t.target_value)
                actual_num = float(t.actual_value) if t.actual_value else None
                if actual_num is not None and target_num != 0:
                    gap = f"{((target_num - actual_num) / target_num) * 100:.1f}%"
            except (ValueError, TypeError):
                pass

            targets_for_prompt.append({
                "metric_name": t.metric_name,
                "target_value": t.target_value,
                "actual_value": t.actual_value or "Unknown",
                "gap": gap,
            })

        # Budget-aware prompt rendering
        budget = self.create_budget()
        budget.reserve("template_chrome", 400)
        budget.reserve("targets", min(len(str(targets_for_prompt)), 500))

        remaining = budget.remaining()
        per_doc_budget = max(200, remaining // max(len(documents), 1))

        doc_list = []
        for d in documents:
            fitted_content = budget.fit(
                f"doc_{d.id}", d.content, max_tokens=per_doc_budget
            )
            doc_list.append({
                "doc_type": d.doc_type,
                "title": d.title,
                "content": fitted_content,
            })

        prompt = self.render_prompt(
            project_name=project.name,
            metric_targets=targets_for_prompt,
            documents=doc_list,
            days_since_launch=days_since_launch,
        )
        budget.log_summary(self.agent_name)

        result_data = await self.call_llm_structured(prompt)

        # 7. Store the gap analysis
        gap_analysis = GapAnalysis(
            project_id=project.id,
            overall_status=result_data.get("overall_status", "unknown"),
            gaps=result_data.get("gaps", []),
            metrics_on_track=result_data.get("metrics_on_track", []),
            executive_summary=result_data.get("executive_summary", ""),
            next_review_date=result_data.get("next_review_date"),
        )
        session.add(gap_analysis)
        await session.flush()

        logger.info(
            "Gap analysis complete for project %s: status=%s, gaps=%d",
            project_id,
            gap_analysis.overall_status,
            len(gap_analysis.gaps),
        )

        return {
            "analysis_id": str(gap_analysis.id),
            "overall_status": gap_analysis.overall_status,
            "gaps": gap_analysis.gaps,
            "metrics_on_track": gap_analysis.metrics_on_track,
            "executive_summary": gap_analysis.executive_summary,
            "next_review_date": gap_analysis.next_review_date,
        }
