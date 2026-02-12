"""SQLAlchemy ORM models for the Helix platform."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class Project(Base):
    """A managed project in Helix."""

    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, default="")
    repo_path = Column(String(500), nullable=True)       # relative to HELIX_WORKSPACE
    github_repo = Column(String(500), nullable=True)      # cloud mode (owner/repo)
    status = Column(
        Enum("active", "launched", "archived", name="project_status"),
        default="active",
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    documents = relationship("Document", back_populates="project", cascade="all, delete-orphan")
    risk_assessments = relationship(
        "RiskAssessment", back_populates="project", cascade="all, delete-orphan"
    )
    launch_checklists = relationship(
        "LaunchChecklist", back_populates="project", cascade="all, delete-orphan"
    )
    metric_targets = relationship(
        "MetricTarget", back_populates="project", cascade="all, delete-orphan"
    )
    scope_check_results = relationship(
        "ScopeCheckResult", back_populates="project", cascade="all, delete-orphan"
    )


class Document(Base):
    """A document (PRD, design doc, meeting notes) linked to a project."""

    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    title = Column(String(500), nullable=False)
    doc_type = Column(
        Enum("prd", "technical_design", "meeting_notes", "other", name="doc_type"),
        nullable=False,
    )
    content = Column(Text, nullable=False)
    metadata_ = Column("metadata", JSONB, default=dict)
    indexed = Column(
        Enum("pending", "processing", "indexed", "failed", name="index_status"),
        default="pending",
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    project = relationship("Project", back_populates="documents")
    risk_assessments = relationship(
        "RiskAssessment", back_populates="document", cascade="all, delete-orphan"
    )


class RiskAssessment(Base):
    """Risk analysis output for a document."""

    __tablename__ = "risk_assessments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    overall_score = Column(Float, default=0.0)
    risks = Column(JSONB, default=list)
    dependencies = Column(JSONB, default=list)
    summary = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    project = relationship("Project", back_populates="risk_assessments")
    document = relationship("Document", back_populates="risk_assessments")


class LaunchChecklist(Base):
    """Pre-filled launch checklist for a project."""

    __tablename__ = "launch_checklists"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    fields = Column(JSONB, default=list)
    warnings = Column(JSONB, default=list)
    missing_information = Column(JSONB, default=list)
    status = Column(
        Enum("draft", "reviewed", "submitted", "approved", name="checklist_status"),
        default="draft",
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    project = relationship("Project", back_populates="launch_checklists")


class MetricTarget(Base):
    """Post-launch metric targets from PRD promises."""

    __tablename__ = "metric_targets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    metric_name = Column(String(255), nullable=False)
    target_value = Column(String(255), nullable=False)
    actual_value = Column(String(255), nullable=True)
    unit = Column(String(50), default="")
    checked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    project = relationship("Project", back_populates="metric_targets")


class HistoricalEvent(Base):
    """Historical events for the risk prediction model."""

    __tablename__ = "historical_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(String(255), nullable=False, index=True)
    team = Column(String(255), nullable=False, index=True)
    duration_days = Column(Integer, nullable=False)
    outcome = Column(String(255), nullable=False)
    description = Column(Text, default="")
    tags = Column(JSONB, default=list)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ScopeCheckResult(Base):
    """Result of a scope-creep check (local branch or cloud PR)."""

    __tablename__ = "scope_check_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)

    # Local mode fields
    base_branch = Column(String(255), nullable=True)
    head_branch = Column(String(255), nullable=True)

    # Cloud mode fields (kept for future use)
    pr_number = Column(Integer, nullable=True)
    repo_name = Column(String(500), nullable=True)

    alignment_score = Column(Float, default=1.0)
    violations = Column(JSONB, default=list)
    summary = Column(Text, default="")
    requires_tpm_approval = Column(
        Enum("yes", "no", name="approval_required"), default="no"
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    project = relationship("Project", back_populates="scope_check_results")


class GapAnalysis(Base):
    """Post-launch gap analysis report."""

    __tablename__ = "gap_analyses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    overall_status = Column(String(50), default="on_track")
    gaps = Column(JSONB, default=list)
    metrics_on_track = Column(JSONB, default=list)
    executive_summary = Column(Text, default="")
    next_review_date = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
