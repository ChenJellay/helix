"""Pydantic schemas for API request/response validation."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# ── Projects ──────────────────────────────────────────────────────────────────


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    github_repo: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    github_repo: str | None = None
    status: str | None = None


class ProjectResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    github_repo: str | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectListResponse(BaseModel):
    projects: list[ProjectResponse]
    total: int


# ── Documents ─────────────────────────────────────────────────────────────────


class DocumentCreate(BaseModel):
    project_id: uuid.UUID
    title: str = Field(..., min_length=1, max_length=500)
    doc_type: str = Field(..., pattern="^(prd|technical_design|meeting_notes|other)$")
    content: str = Field(..., min_length=1)
    metadata: dict | None = None


class DocumentResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    doc_type: str
    content: str
    metadata_: dict | None = Field(None, alias="metadata_")
    indexed: str
    created_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


# ── Risk Assessments ──────────────────────────────────────────────────────────


class RiskItem(BaseModel):
    risk: str
    trigger_text: str = ""
    probability: float = 0.0
    impact: str = "medium"
    blocking_team: str = ""
    mitigation: str = ""
    historical_evidence: str | None = None


class DependencyItem(BaseModel):
    source: str
    target: str
    type: str = "hard"
    description: str = ""


class RiskAssessmentResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    document_id: uuid.UUID
    overall_score: float
    risks: list[dict]
    dependencies: list[dict]
    summary: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Launch Checklists ─────────────────────────────────────────────────────────


class ChecklistFieldItem(BaseModel):
    field_name: str
    value: str
    confidence: float = 0.0
    evidence: str = ""
    needs_human_review: bool = True


class LaunchChecklistResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    fields: list[dict]
    warnings: list[str]
    missing_information: list[str]
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Scope Check ───────────────────────────────────────────────────────────────


class ViolationItem(BaseModel):
    file: str
    violation_type: str
    severity: str = "warning"
    description: str
    design_reference: str = ""
    recommendation: str = ""


class ScopeCheckResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    pr_number: int
    repo_name: str
    alignment_score: float
    violations: list[dict]
    summary: str
    requires_tpm_approval: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Gap Analysis ──────────────────────────────────────────────────────────────


class GapItem(BaseModel):
    metric_name: str
    target: str
    actual: str
    gap_percentage: float = 0.0
    root_causes: list[str] = []
    recommendations: list[str] = []
    effort_estimate: str = "medium"
    priority: str = "p1"


class GapAnalysisResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    overall_status: str
    gaps: list[dict]
    metrics_on_track: list[str]
    executive_summary: str
    next_review_date: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Metric Targets ────────────────────────────────────────────────────────────


class MetricTargetCreate(BaseModel):
    project_id: uuid.UUID
    metric_name: str
    target_value: str
    unit: str = ""


class MetricTargetUpdate(BaseModel):
    actual_value: str | None = None


class MetricTargetResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    metric_name: str
    target_value: str
    actual_value: str | None
    unit: str
    checked_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Webhooks ──────────────────────────────────────────────────────────────────


class GitHubWebhookPayload(BaseModel):
    """Simplified GitHub PR webhook payload."""

    action: str
    number: int
    pull_request: dict
    repository: dict
