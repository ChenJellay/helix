"""Project CRUD API routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from helix.api.deps import get_db, verify_api_key
from helix.models.db import Project
from helix.models.schemas import (
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
)
from helix.rag.graph import add_project_node

router = APIRouter()


@router.post("/projects", response_model=ProjectResponse, status_code=201)
async def create_project(
    data: ProjectCreate,
    session: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """Create a new project."""
    # Normalise repo_path to workspace-relative if an absolute path was given
    normalised_repo_path = data.repo_path
    if normalised_repo_path:
        from helix.integrations.path_resolver import repo_path_resolver
        try:
            normalised_repo_path = repo_path_resolver.to_relative(normalised_repo_path)
        except ValueError:
            # Already relative or validation will be deferred — store as-is
            pass

    project = Project(
        name=data.name,
        description=data.description,
        repo_path=normalised_repo_path,
        github_repo=data.github_repo,
    )
    session.add(project)
    await session.flush()

    # Add project node to the knowledge graph
    try:
        await add_project_node(str(project.id), project.name)
    except Exception:
        pass  # Graph is optional - don't fail the API call

    await session.refresh(project)
    return project


@router.get("/projects", response_model=ProjectListResponse)
async def list_projects(
    skip: int = 0,
    limit: int = 50,
    session: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """List all projects."""
    result = await session.execute(
        select(Project).order_by(Project.created_at.desc()).offset(skip).limit(limit)
    )
    projects = result.scalars().all()

    count_result = await session.execute(select(Project))
    total = len(count_result.scalars().all())

    return ProjectListResponse(projects=projects, total=total)


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """Get a project by ID."""
    result = await session.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.patch("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID,
    data: ProjectUpdate,
    session: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """Update a project."""
    result = await session.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(project, key, value)

    await session.flush()
    await session.refresh(project)
    return project


@router.delete("/projects/{project_id}", status_code=204)
async def delete_project(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """Delete a project."""
    result = await session.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    await session.delete(project)
