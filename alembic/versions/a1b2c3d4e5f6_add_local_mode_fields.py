"""add local mode fields

Revision ID: a1b2c3d4e5f6
Revises: 5a6d515f827d
Create Date: 2026-02-10 18:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "5a6d515f827d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Project: add repo_path (local mode)
    op.add_column(
        "projects",
        sa.Column("repo_path", sa.String(length=500), nullable=True),
    )

    # ScopeCheckResult: add local branch fields, relax pr_number / repo_name
    op.add_column(
        "scope_check_results",
        sa.Column("base_branch", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "scope_check_results",
        sa.Column("head_branch", sa.String(length=255), nullable=True),
    )
    op.alter_column(
        "scope_check_results",
        "pr_number",
        existing_type=sa.Integer(),
        nullable=True,
    )
    op.alter_column(
        "scope_check_results",
        "repo_name",
        existing_type=sa.String(length=500),
        nullable=True,
    )


def downgrade() -> None:
    # Reverse: drop new columns, re-tighten nullable constraints
    op.alter_column(
        "scope_check_results",
        "repo_name",
        existing_type=sa.String(length=500),
        nullable=False,
    )
    op.alter_column(
        "scope_check_results",
        "pr_number",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.drop_column("scope_check_results", "head_branch")
    op.drop_column("scope_check_results", "base_branch")
    op.drop_column("projects", "repo_path")
