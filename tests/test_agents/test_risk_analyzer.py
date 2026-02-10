"""Tests for the Risk Analyzer agent."""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from helix.agents.risk_analyzer import RiskAnalyzerAgent


class TestRiskAnalyzerAgent:
    """Tests for the Risk Analyzer agent."""

    @pytest.mark.asyncio
    async def test_analyze_returns_assessment(
        self, mock_llm, sample_prd_content, sample_risk_response
    ):
        """Test that analyze processes a document and returns risk assessment."""
        # Mock the LLM to return our sample risk response
        mock_llm.complete.return_value.content = json.dumps(sample_risk_response)
        mock_llm.embed.return_value = [[0.0] * 384]

        # Mock the database session
        mock_session = AsyncMock()
        mock_doc = MagicMock()
        mock_doc.id = uuid.uuid4()
        mock_doc.project_id = uuid.uuid4()
        mock_doc.content = sample_prd_content

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_doc
        mock_session.execute.return_value = mock_result

        # Mock scalars for historical events
        mock_scalars = MagicMock()
        mock_scalars.scalars.return_value.all.return_value = []
        mock_session.execute.side_effect = [mock_result, mock_scalars]

        agent = RiskAnalyzerAgent(llm=mock_llm)

        with (
            patch(
                "helix.agents.risk_analyzer.retrieve_similar_documents",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch("helix.agents.risk_analyzer.graph") as mock_graph,
        ):
            mock_graph.add_dependency = AsyncMock()

            result = await agent.analyze(
                document_id=str(mock_doc.id),
                session=mock_session,
            )

        assert "assessment_id" in result
        assert result["overall_score"] == 0.65
        assert len(result["risks"]) == 1
        assert result["risks"][0]["blocking_team"] == "Privacy"
