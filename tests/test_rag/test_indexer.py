"""Tests for the document indexer."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from helix.rag.indexer import index_document, _parse_json_response, _regex_entity_fallback


class TestParseJsonResponse:
    """Tests for JSON response parsing."""

    def test_plain_json(self):
        result = _parse_json_response('{"key": "value"}')
        assert result == {"key": "value"}

    def test_json_with_code_fence(self):
        result = _parse_json_response('```json\n{"key": "value"}\n```')
        assert result == {"key": "value"}

    def test_json_with_bare_fence(self):
        result = _parse_json_response('```\n{"key": "value"}\n```')
        assert result == {"key": "value"}

    def test_invalid_json(self):
        result = _parse_json_response("not json at all")
        assert result == {}


class TestRegexEntityFallback:
    """Tests for the regex-based entity extraction fallback."""

    def test_extracts_capitalized_phrases(self):
        text = "The Privacy Team approved the Data Privacy Review."
        entities = _regex_entity_fallback(text)
        names = [e["name"] for e in entities]
        assert "Privacy Team" in names
        assert "Data Privacy Review" in names

    def test_caps_only(self):
        text = "no capitalized multi-word terms here"
        entities = _regex_entity_fallback(text)
        assert len(entities) == 0

    def test_deduplication(self):
        text = "Privacy Team met. The Privacy Team approved."
        entities = _regex_entity_fallback(text)
        names = [e["name"] for e in entities]
        assert names.count("Privacy Team") == 1


class TestIndexDocument:
    """Tests for the full indexing pipeline."""

    @pytest.mark.asyncio
    async def test_index_document_chunks_and_stores(self, mock_llm):
        """Verify the indexing pipeline calls vector and graph stores."""
        with (
            patch("helix.rag.indexer.get_llm", return_value=mock_llm),
            patch("helix.rag.indexer.vector") as mock_vector,
            patch("helix.rag.indexer.graph") as mock_graph,
        ):
            mock_vector.add_documents = AsyncMock()
            mock_graph.add_document_node = AsyncMock()
            mock_graph.add_entity = AsyncMock()

            # Mock entity extraction response
            mock_llm.complete.return_value.content = json.dumps({
                "entities": [
                    {"name": "Privacy Team", "type": "team"},
                    {"name": "Payments API", "type": "api"},
                ]
            })
            mock_llm.embed.return_value = [[0.0] * 384] * 5

            result = await index_document(
                doc_id="test-doc-1",
                project_id="test-proj-1",
                title="Test PRD",
                doc_type="prd",
                content="A short test document about the Privacy Team and Payments API.",
            )

            assert result["doc_id"] == "test-doc-1"
            assert result["chunks"] >= 1
            assert result["entities"] == 2

            mock_vector.add_documents.assert_called_once()
            mock_graph.add_document_node.assert_called_once()
            assert mock_graph.add_entity.call_count == 2
