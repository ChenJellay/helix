"""Tests for the BaseAgent class."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from helix.agents.base import BaseAgent


class ConcreteAgent(BaseAgent):
    """Concrete implementation for testing the abstract BaseAgent."""

    agent_name = "test_agent"
    prompt_template = "risk_analysis.j2"


class TestBaseAgent:
    """Tests for BaseAgent shared functionality."""

    def test_parse_json_valid(self):
        result = BaseAgent.parse_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_parse_json_with_fences(self):
        result = BaseAgent.parse_json('```json\n{"key": "value"}\n```')
        assert result == {"key": "value"}

    def test_parse_json_invalid(self):
        result = BaseAgent.parse_json("not json")
        assert "error" in result
        assert "raw" in result

    @pytest.mark.asyncio
    async def test_call_llm(self, mock_llm):
        """Test that call_llm sends messages and returns content."""
        mock_llm.complete.return_value.content = "test response"

        agent = ConcreteAgent(llm=mock_llm)
        result = await agent.call_llm("Hello")

        assert result == "test response"
        mock_llm.complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_llm_structured(self, mock_llm):
        """Test that call_llm_structured parses JSON."""
        mock_llm.complete.return_value.content = '{"result": "ok"}'

        agent = ConcreteAgent(llm=mock_llm)
        result = await agent.call_llm_structured("Analyze this")

        assert result == {"result": "ok"}

    def test_render_prompt(self):
        """Test Jinja2 template rendering."""
        agent = ConcreteAgent()
        prompt = agent.render_prompt(
            prd_content="Test PRD",
            historical_events=[],
            similar_docs=[],
        )
        assert "Test PRD" in prompt
        assert "risk" in prompt.lower()
