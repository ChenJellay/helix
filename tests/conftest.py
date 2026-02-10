"""Shared test fixtures for the Helix test suite."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from helix.llm.base import LLMResponse


@pytest.fixture
def mock_llm():
    """Create a mock LLM that returns predictable responses."""
    llm = AsyncMock()
    llm.model = "test-model"

    # Default completion response
    llm.complete.return_value = LLMResponse(
        content='{"result": "mock response"}',
        model="test-model",
        usage={"prompt_tokens": 10, "completion_tokens": 20},
    )

    # Default embedding response (384-dim zero vectors)
    llm.embed.return_value = [[0.0] * 384]

    return llm


@pytest.fixture
def sample_project_id():
    """Return a consistent sample project UUID."""
    return str(uuid.UUID("12345678-1234-5678-1234-567812345678"))


@pytest.fixture
def sample_document_id():
    """Return a consistent sample document UUID."""
    return str(uuid.UUID("abcdefab-cdef-abcd-efab-cdefabcdefab"))


@pytest.fixture
def sample_prd_content():
    """Return a sample PRD for testing."""
    return """
# PRD: Test Feature

## Overview
This feature will collect user preferences to improve recommendations.

## Dependencies
- Search Team: Recommendations API
- Privacy Team: Data Privacy Review required

## Success Metrics
- User engagement: +15%
- Latency: < 500ms p50
"""


@pytest.fixture
def sample_risk_response():
    """Return a sample risk analysis LLM response."""
    return {
        "overall_risk_score": 0.65,
        "risks": [
            {
                "risk": "Privacy review required for user data collection",
                "trigger_text": "collect user preferences",
                "probability": 0.8,
                "impact": "high",
                "blocking_team": "Privacy",
                "mitigation": "Start DPR process immediately",
                "historical_evidence": "85% of similar features required DPR",
            }
        ],
        "dependencies": [
            {
                "source": "Test Feature",
                "target": "Search Team",
                "type": "hard",
                "description": "Requires Recommendations API",
            }
        ],
        "summary": "Medium-high risk due to privacy implications.",
    }


@pytest.fixture
def sample_scope_check_response():
    """Return a sample scope check LLM response."""
    return {
        "alignment_score": 0.6,
        "violations": [
            {
                "file": "src/api/location.py",
                "violation_type": "scope_creep",
                "severity": "warning",
                "description": "Network call not in design doc",
                "design_reference": "Design specifies local storage only",
                "recommendation": "Remove external API call or update design doc",
            }
        ],
        "summary": "PR introduces external dependency not in design.",
        "requires_tpm_approval": True,
    }


@pytest.fixture
def sample_launch_response():
    """Return a sample launch checklist LLM response."""
    return {
        "fields": [
            {
                "field_name": "Feature description",
                "value": "User preference collection for recommendations",
                "confidence": 0.9,
                "evidence": "Extracted from PRD overview section",
                "needs_human_review": False,
            },
            {
                "field_name": "Does this feature collect user data?",
                "value": "Yes",
                "confidence": 0.95,
                "evidence": "PRD mentions 'collect user preferences'",
                "needs_human_review": True,
            },
        ],
        "warnings": ["Privacy review status unknown"],
        "missing_information": ["Rollback plan not found in project documents"],
    }


@pytest.fixture
def sample_gap_response():
    """Return a sample gap analysis LLM response."""
    return {
        "overall_status": "at_risk",
        "gaps": [
            {
                "metric_name": "User engagement",
                "target": "+15%",
                "actual": "+5%",
                "gap_percentage": 66.7,
                "root_causes": ["Low feature discoverability"],
                "recommendations": ["Add onboarding tooltip"],
                "effort_estimate": "low",
                "priority": "p1",
            }
        ],
        "metrics_on_track": ["Latency"],
        "executive_summary": "Feature is at risk of missing engagement targets.",
        "next_review_date": "2026-03-15",
    }
