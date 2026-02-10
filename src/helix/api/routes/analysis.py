"""Gap analysis and risk assessment API routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from helix.agents.gap_analyzer import GapAnalyzerAgent
from helix.agents.risk_analyzer import RiskAnalyzerAgent
from helix.api.deps import get_db, verify_api_key
from helix.models.db import Document, GapAnalysis, Project, RiskAssessment, ScopeCheckResult
from helix.models.schemas import (
    GapAnalysisResponse,
    RiskAssessmentResponse,
    ScopeCheckResponse,
)

router = APIRouter()


# ── Risk Assessments ──────────────────────────────────────────────────────────


@router.post(
    "/analysis/risk/{document_id}",
    response_model=RiskAssessmentResponse,
)
async def trigger_risk_analysis(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """Manually trigger risk analysis on a document."""
    # Verify document exists
    doc_result = await session.execute(
        select(Document).where(Document.id == document_id)
    )
    document = doc_result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    agent = RiskAnalyzerAgent()
    result = await agent.analyze(document_id=str(document_id), session=session)

    await session.commit()

    # Fetch and return the created assessment
    assessment_result = await session.execute(
        select(RiskAssessment).where(RiskAssessment.id == result["assessment_id"])
    )
    return assessment_result.scalar_one()


@router.get(
    "/projects/{project_id}/risks",
    response_model=list[RiskAssessmentResponse],
)
async def list_risk_assessments(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """List all risk assessments for a project."""
    result = await session.execute(
        select(RiskAssessment)
        .where(RiskAssessment.project_id == project_id)
        .order_by(RiskAssessment.created_at.desc())
    )
    return result.scalars().all()


# ── Scope Check Results ───────────────────────────────────────────────────────


@router.get(
    "/projects/{project_id}/scope-checks",
    response_model=list[ScopeCheckResponse],
)
async def list_scope_checks(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """List all scope check results for a project."""
    result = await session.execute(
        select(ScopeCheckResult)
        .where(ScopeCheckResult.project_id == project_id)
        .order_by(ScopeCheckResult.created_at.desc())
    )
    return result.scalars().all()


# ── Gap Analysis ──────────────────────────────────────────────────────────────


@router.get(
    "/analysis/{project_id}/gap",
    response_model=GapAnalysisResponse | None,
)
async def get_latest_gap_analysis(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """Get the most recent gap analysis for a project."""
    # Verify project exists
    proj_result = await session.execute(
        select(Project).where(Project.id == project_id)
    )
    if not proj_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    result = await session.execute(
        select(GapAnalysis)
        .where(GapAnalysis.project_id == project_id)
        .order_by(GapAnalysis.created_at.desc())
        .limit(1)
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        return None
    return analysis


@router.post(
    "/analysis/{project_id}/gap",
    response_model=GapAnalysisResponse,
)
async def trigger_gap_analysis(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """Manually trigger a gap analysis for a project."""
    # Verify project exists
    proj_result = await session.execute(
        select(Project).where(Project.id == project_id)
    )
    if not proj_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    agent = GapAnalyzerAgent()
    result = await agent.analyze_gaps(
        project_id=str(project_id),
        session=session,
    )

    if result.get("status") == "no_targets":
        raise HTTPException(
            status_code=400,
            detail="No metric targets defined for this project.",
        )

    # Fetch and return the created analysis
    analysis_result = await session.execute(
        select(GapAnalysis).where(GapAnalysis.id == result["analysis_id"])
    )
    return analysis_result.scalar_one()
