"""Tests for the LLM base interface and router."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from helix.llm.base import BaseLLM, LLMResponse
from helix.llm.router import LLMRouter, get_llm


class TestLLMResponse:
    """Tests for the LLMResponse model."""

    def test_basic_response(self):
        resp = LLMResponse(content="Hello", model="test", usage={})
        assert resp.content == "Hello"
        assert resp.model == "test"

    def test_response_with_usage(self):
        resp = LLMResponse(
            content="Hi",
            model="gpt-4o",
            usage={"prompt_tokens": 10, "completion_tokens": 5},
        )
        assert resp.usage["prompt_tokens"] == 10

    def test_response_with_raw(self):
        resp = LLMResponse(
            content="test",
            model="test",
            usage={},
            raw={"id": "chatcmpl-123"},
        )
        assert resp.raw["id"] == "chatcmpl-123"


class TestLLMRouter:
    """Tests for the LLMRouter provider routing."""

    @pytest.mark.asyncio
    async def test_complete_calls_litellm(self, mock_llm):
        """Test that complete delegates to litellm."""
        mock_litellm = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "test response"
        mock_response.usage = MagicMock()
        mock_response.usage.__iter__ = MagicMock(return_value=iter([]))
        mock_response.model_dump.return_value = {}

        mock_litellm.acompletion = AsyncMock(return_value=mock_response)
        mock_litellm.drop_params = True

        with patch.dict("sys.modules", {"litellm": mock_litellm}):
            router = LLMRouter(model="gpt-4o")
            result = await router.complete(
                messages=[{"role": "user", "content": "Hello"}]
            )

            assert result.content == "test response"
            mock_litellm.acompletion.assert_called_once()

    @pytest.mark.asyncio
    async def test_embed_calls_litellm(self):
        """Test that embed delegates to litellm."""
        mock_litellm = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [{"embedding": [0.1, 0.2, 0.3]}]
        mock_litellm.aembedding = AsyncMock(return_value=mock_response)

        with patch.dict("sys.modules", {"litellm": mock_litellm}):
            router = LLMRouter(model="gpt-4o")
            result = await router.embed(["test text"])

            assert result == [[0.1, 0.2, 0.3]]

    def test_resolve_model_name_openai(self):
        """OpenAI models should not be prefixed."""
        with patch("helix.llm.router.settings") as mock_settings:
            mock_settings.llm_provider = "openai"
            mock_settings.llm_model = "gpt-4o"
            mock_settings.openai_api_key = "test"

            router = LLMRouter(model="gpt-4o")
            assert router._resolve_model_name() == "gpt-4o"

    def test_resolve_model_name_anthropic(self):
        """Anthropic models should be prefixed with 'anthropic/'."""
        with patch("helix.llm.router.settings") as mock_settings:
            mock_settings.llm_provider = "anthropic"
            mock_settings.llm_model = "claude-sonnet-4-20250514"
            mock_settings.anthropic_api_key = "test"

            router = LLMRouter(model="claude-sonnet-4-20250514")
            assert router._resolve_model_name() == "anthropic/claude-sonnet-4-20250514"


class TestGetLLM:
    """Tests for the get_llm singleton factory."""

    def test_get_llm_returns_router(self):
        """get_llm should return an LLMRouter instance."""
        with patch("helix.llm.router._llm_instance", None):
            llm = get_llm()
            assert isinstance(llm, LLMRouter)

    def test_get_llm_singleton(self):
        """Multiple calls should return the same instance."""
        with patch("helix.llm.router._llm_instance", None):
            llm1 = get_llm()
            llm2 = get_llm()
            assert llm1 is llm2
