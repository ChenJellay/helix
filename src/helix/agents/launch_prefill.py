"""Launch Prefill Agent - Stage 3: LaunchCal Automation.

Pre-fills launch checklists based on project artifacts, risk assessments,
and CI/CD metrics.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from helix.agents.base import BaseAgent
from helix.integrations.metrics import MetricsClient
from helix.models.db import Document, LaunchChecklist, Project, RiskAssessment

logger = logging.getLogger(__name__)


class LaunchPrefillAgent(BaseAgent):
    """Pre-fills launch checklists from project artifacts."""

    agent_name = "launch_prefill"
    prompt_template = "launch_prefill.j2"

    def __init__(self, metrics_client: MetricsClient | None = None, **kwargs):
        super().__init__(**kwargs)
        self.metrics = metrics_client or MetricsClient()

    async def generate_checklist(
        self,
        project_id: str,
        session: AsyncSession,
    ) -> dict[str, Any]:
        """Generate a pre-filled launch checklist for a project.

        Args:
            project_id: UUID of the project.
            session: Active database session.

        Returns:
            Launch checklist data.
        """
        # 1. Fetch project
        result = await session.execute(
            select(Project).where(Project.id == project_id)
        )
        project = result.scalar_one_or_none()
        if not project:
            raise ValueError(f"Project {project_id} not found")

        # 2. Fetch all project documents
        docs_result = await session.execute(
            select(Document).where(Document.project_id == project_id)
        )
        documents = docs_result.scalars().all()

        # 3. Fetch risk assessments
        risk_result = await session.execute(
            select(RiskAssessment).where(RiskAssessment.project_id == project_id)
        )
        risk_assessments = risk_result.scalars().all()

        # Flatten risks from all assessments
        all_risks = []
        for ra in risk_assessments:
            all_risks.extend(ra.risks if isinstance(ra.risks, list) else [])

        # 4. Fetch CI/CD metrics (stub)
        metrics = await self.metrics.get_project_metrics(project.github_repo or "")

        # 5. Budget-aware prompt rendering
        budget = self.create_budget()
        budget.reserve("template_chrome", 500)
        budget.reserve("risks", min(len(str(all_risks)), 400))
        budget.reserve("metrics", 200)

        # Distribute remaining budget across documents
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
            documents=doc_list,
            risk_assessments=all_risks,
            metrics=metrics,
        )
        budget.log_summary(self.agent_name)

        result_data = await self.call_llm_structured(prompt)

        # 6. Store the launch checklist
        checklist = LaunchChecklist(
            project_id=project.id,
            fields=result_data.get("fields", []),
            warnings=result_data.get("warnings", []),
            missing_information=result_data.get("missing_information", []),
            status="draft",
        )
        session.add(checklist)
        await session.flush()

        logger.info(
            "Launch checklist generated for project %s: %d fields, %d warnings",
            project_id,
            len(checklist.fields),
            len(checklist.warnings),
        )

        return {
            "checklist_id": str(checklist.id),
            "fields": checklist.fields,
            "warnings": checklist.warnings,
            "missing_information": checklist.missing_information,
            "status": checklist.status,
        }
