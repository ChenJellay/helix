"""Risk Analyzer Agent - Stage 1: Discovery & Architecture.

Scans PRDs against historical risk patterns and predicts launch blockers.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from helix.agents.base import BaseAgent
from helix.config import settings
from helix.models.db import Document, HistoricalEvent, RiskAssessment
from helix.rag import graph
from helix.rag.retriever import retrieve_similar_documents

logger = logging.getLogger(__name__)


class RiskAnalyzerAgent(BaseAgent):
    """Analyzes PRDs for risks based on historical patterns."""

    agent_name = "risk_analyzer"
    prompt_template = "risk_analysis.j2"

    async def analyze(
        self,
        document_id: str,
        session: AsyncSession,
    ) -> dict[str, Any]:
        """Run risk analysis on a document.

        Args:
            document_id: UUID of the uploaded document.
            session: Active database session.

        Returns:
            Risk assessment results dict.
        """
        # 1. Fetch the document
        result = await session.execute(
            select(Document).where(Document.id == document_id)
        )
        document = result.scalar_one_or_none()
        if not document:
            raise ValueError(f"Document {document_id} not found")

        prd_content = document.content
        project_id = str(document.project_id)

        # 2. Retrieve historical events (fewer on SLM to save tokens)
        event_limit = 10 if settings.is_slm else 20
        historical_events = await self._get_historical_events(session, limit=event_limit)

        # 3. Retrieve similar past documents
        top_k = settings.active_slm_profile.get("retrieval_top_k", 5)
        similar_docs = await retrieve_similar_documents(
            query=prd_content[:1000],
            n_results=top_k,
        )

        # 4. Budget-aware prompt rendering
        budget = self.create_budget()
        budget.reserve("template_chrome", 400)  # instructions + JSON schema
        budget.reserve("historical", min(len(str(historical_events)), 600))

        prd_fitted = budget.fit("prd_content", prd_content)

        prompt = self.render_prompt(
            prd_content=prd_fitted,
            historical_events=historical_events,
            similar_docs=[
                {"title": d["metadata"].get("title", "Unknown"), "summary": d["content"][:200]}
                for d in similar_docs
            ],
        )
        budget.log_summary(self.agent_name)

        result_data = await self.call_llm_structured(prompt)

        # 5. Store the risk assessment
        assessment = RiskAssessment(
            project_id=document.project_id,
            document_id=document.id,
            overall_score=result_data.get("overall_risk_score", 0.0),
            risks=result_data.get("risks", []),
            dependencies=result_data.get("dependencies", []),
            summary=result_data.get("summary", ""),
        )
        session.add(assessment)

        # 6. Store dependencies in the knowledge graph
        for dep in result_data.get("dependencies", []):
            target = dep.get("target", "")
            if target:
                await graph.add_dependency(
                    source_project_id=project_id,
                    target_entity=target,
                    dep_type=dep.get("type", "hard"),
                    description=dep.get("description", ""),
                )

        await session.flush()

        logger.info(
            "Risk analysis complete for doc %s: score=%.2f, risks=%d, deps=%d",
            document_id,
            assessment.overall_score,
            len(assessment.risks),
            len(assessment.dependencies),
        )

        return {
            "assessment_id": str(assessment.id),
            "overall_score": assessment.overall_score,
            "risks": assessment.risks,
            "dependencies": assessment.dependencies,
            "summary": assessment.summary,
        }

    async def _get_historical_events(
        self, session: AsyncSession, limit: int = 20
    ) -> list[dict[str, Any]]:
        """Fetch recent historical events for risk context."""
        result = await session.execute(
            select(HistoricalEvent)
            .order_by(HistoricalEvent.created_at.desc())
            .limit(limit)
        )
        events = result.scalars().all()
        return [
            {
                "event_type": e.event_type,
                "team": e.team,
                "duration_days": e.duration_days,
                "outcome": e.outcome,
                "description": e.description,
            }
            for e in events
        ]
