"""Tests for the health check endpoint and basic app setup."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client with mocked dependencies."""
    with (
        patch("helix.db.session.init_db", new_callable=AsyncMock),
        patch("helix.rag.vector.get_chroma_client"),
        patch("helix.rag.graph.get_neo4j_driver"),
        patch("helix.tasks.workers.start_scheduler"),
        patch("helix.db.session.close_db", new_callable=AsyncMock),
        patch("helix.rag.graph.close_neo4j_driver"),
        patch("helix.tasks.workers.stop_scheduler"),
    ):
        from helix.main import app

        with TestClient(app) as c:
            yield c


class TestHealthEndpoint:
    """Tests for the /health endpoint."""

    def test_health_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_response_body(self, client):
        response = client.get("/health")
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "0.1.0"
        assert "env" in data
