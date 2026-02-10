"""Launch checklist API routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from helix.agents.launch_prefill import LaunchPrefillAgent
from helix.api.deps import get_db, verify_api_key
from helix.models.db import LaunchChecklist, Project
from helix.models.schemas import LaunchChecklistResponse

router = APIRouter()


@router.get(
    "/launch/{project_id}/checklist",
    response_model=LaunchChecklistResponse,
)
async def get_or_generate_checklist(
    project_id: uuid.UUID,
    regenerate: bool = False,
    session: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """Get or generate a launch checklist for a project.

    If a draft checklist already exists and regenerate=False, returns it.
    Otherwise generates a new one via the Launch Prefill agent.
    """
    # Verify project exists
    proj_result = await session.execute(
        select(Project).where(Project.id == project_id)
    )
    if not proj_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    # Check for existing draft
    if not regenerate:
        existing = await session.execute(
            select(LaunchChecklist)
            .where(
                LaunchChecklist.project_id == project_id,
                LaunchChecklist.status == "draft",
            )
            .order_by(LaunchChecklist.created_at.desc())
            .limit(1)
        )
        checklist = existing.scalar_one_or_none()
        if checklist:
            return checklist

    # Generate a new checklist
    agent = LaunchPrefillAgent()
    result = await agent.generate_checklist(
        project_id=str(project_id),
        session=session,
    )

    # Fetch and return the created checklist
    cl_result = await session.execute(
        select(LaunchChecklist).where(LaunchChecklist.id == result["checklist_id"])
    )
    return cl_result.scalar_one()


@router.patch(
    "/launch/{project_id}/checklist/{checklist_id}",
    response_model=LaunchChecklistResponse,
)
async def update_checklist(
    project_id: uuid.UUID,
    checklist_id: uuid.UUID,
    fields: list[dict] | None = None,
    status: str | None = None,
    session: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """Update a launch checklist (e.g., after human review)."""
    result = await session.execute(
        select(LaunchChecklist).where(
            LaunchChecklist.id == checklist_id,
            LaunchChecklist.project_id == project_id,
        )
    )
    checklist = result.scalar_one_or_none()
    if not checklist:
        raise HTTPException(status_code=404, detail="Checklist not found")

    if fields is not None:
        checklist.fields = fields
    if status is not None:
        checklist.status = status

    await session.flush()
    await session.refresh(checklist)
    return checklist
