"""Document upload and management API routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from helix.api.deps import get_db, verify_api_key
from helix.models.db import Document, Project
from helix.models.schemas import DocumentCreate, DocumentResponse

router = APIRouter()


async def _index_and_analyze(document_id: str, project_id: str) -> None:
    """Background task: index the document and run risk analysis."""
    from helix.db.session import async_session_factory
    from helix.rag.indexer import index_document
    from helix.agents.risk_analyzer import RiskAnalyzerAgent

    async with async_session_factory() as session:
        # Fetch the document
        result = await session.execute(
            select(Document).where(Document.id == document_id)
        )
        document = result.scalar_one_or_none()
        if not document:
            return

        try:
            # Update status to processing
            document.indexed = "processing"
            await session.commit()

            # Index the document
            await index_document(
                doc_id=str(document.id),
                project_id=str(document.project_id),
                title=document.title,
                doc_type=document.doc_type,
                content=document.content,
            )

            # Run risk analysis for PRDs
            if document.doc_type in ("prd", "technical_design"):
                agent = RiskAnalyzerAgent()
                await agent.analyze(document_id=str(document.id), session=session)

            document.indexed = "indexed"
            await session.commit()

        except Exception as e:
            document.indexed = "failed"
            await session.commit()
            raise e


@router.post("/documents", response_model=DocumentResponse, status_code=201)
async def upload_document(
    data: DocumentCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """Upload a document (PRD, design doc, meeting notes).

    The document is stored immediately and indexing + risk analysis
    runs asynchronously in the background.
    """
    # Verify project exists
    proj_result = await session.execute(
        select(Project).where(Project.id == data.project_id)
    )
    if not proj_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    document = Document(
        project_id=data.project_id,
        title=data.title,
        doc_type=data.doc_type,
        content=data.content,
        metadata_=data.metadata or {},
        indexed="pending",
    )
    session.add(document)
    await session.flush()
    await session.refresh(document)

    # Trigger background indexing and analysis
    background_tasks.add_task(
        _index_and_analyze,
        document_id=str(document.id),
        project_id=str(document.project_id),
    )

    return document


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """Get a document by ID."""
    result = await session.execute(
        select(Document).where(Document.id == document_id)
    )
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.get("/projects/{project_id}/documents", response_model=list[DocumentResponse])
async def list_project_documents(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """List all documents for a project."""
    result = await session.execute(
        select(Document)
        .where(Document.project_id == project_id)
        .order_by(Document.created_at.desc())
    )
    return result.scalars().all()
