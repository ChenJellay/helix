"""Tests for the projects API routes."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestProjectSchemas:
    """Test Pydantic schema validation for projects."""

    def test_project_create_valid(self):
        from helix.models.schemas import ProjectCreate

        data = ProjectCreate(name="Test Project", description="A test", github_repo="o/r")
        assert data.name == "Test Project"
        assert data.github_repo == "o/r"

    def test_project_create_requires_name(self):
        from helix.models.schemas import ProjectCreate

        with pytest.raises(Exception):
            ProjectCreate(name="", description="test")

    def test_project_update_partial(self):
        from helix.models.schemas import ProjectUpdate

        data = ProjectUpdate(name="New Name")
        dump = data.model_dump(exclude_unset=True)
        assert "name" in dump
        assert "description" not in dump


class TestDocumentSchemas:
    """Test Pydantic schema validation for documents."""

    def test_document_create_valid(self):
        from helix.models.schemas import DocumentCreate

        data = DocumentCreate(
            project_id=uuid.uuid4(),
            title="Test Doc",
            doc_type="prd",
            content="Some content",
        )
        assert data.doc_type == "prd"

    def test_document_create_invalid_type(self):
        from helix.models.schemas import DocumentCreate

        with pytest.raises(Exception):
            DocumentCreate(
                project_id=uuid.uuid4(),
                title="Test",
                doc_type="invalid_type",
                content="content",
            )
