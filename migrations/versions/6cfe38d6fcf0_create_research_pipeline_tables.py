"""create research pipeline tables

Revision ID: 6cfe38d6fcf0
Revises:
Create Date: 2026-10-04 13:11:48.148807

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "6cfe38d6fcf0"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.create_table(
        "research_jobs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        op.f("ix_research_jobs_status"),
        "research_jobs",
        ["status"],
        unique=False,
    )

    op.create_table(
        "reports",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("executive_summary", sa.Text(), nullable=False),
        sa.Column(
            "key_findings",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("detailed_analysis", sa.Text(), nullable=False),
        sa.Column("conclusion", sa.Text(), nullable=False),
        sa.Column(
            "trade_offs",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "limitations",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["research_jobs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        op.f("ix_reports_job_id"),
        "reports",
        ["job_id"],
        unique=True,
    )

    op.create_table(
        "research_tasks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column(
            "search_queries",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["research_jobs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        op.f("ix_research_tasks_job_id"),
        "research_tasks",
        ["job_id"],
        unique=False,
    )

    op.create_index(
        op.f("ix_research_tasks_status"),
        "research_tasks",
        ["status"],
        unique=False,
    )

    op.create_table(
        "sources",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["research_jobs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "job_id",
            "url",
            name="uq_sources_job_url",
        ),
    )

    op.create_index(
        op.f("ix_sources_job_id"),
        "sources",
        ["job_id"],
        unique=False,
    )

    op.create_table(
        "evidence",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column("claim", sa.Text(), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["sources.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        op.f("ix_evidence_source_id"),
        "evidence",
        ["source_id"],
        unique=False,
    )

    op.create_table(
        "report_evaluations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("report_id", sa.UUID(), nullable=False),
        sa.Column("iteration", sa.Integer(), nullable=False),
        sa.Column("grounded", sa.Boolean(), nullable=False),
        sa.Column("citation_correct", sa.Boolean(), nullable=False),
        sa.Column("hallucination_detected", sa.Boolean(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("reasoning", sa.Text(), nullable=False),
        sa.Column(
            "unsupported_claims",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["research_jobs.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["reports.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        op.f("ix_report_evaluations_job_id"),
        "report_evaluations",
        ["job_id"],
        unique=False,
    )

    op.create_index(
        op.f("ix_report_evaluations_report_id"),
        "report_evaluations",
        ["report_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_index(
        op.f("ix_report_evaluations_report_id"),
        table_name="report_evaluations",
    )

    op.drop_index(
        op.f("ix_report_evaluations_job_id"),
        table_name="report_evaluations",
    )

    op.drop_table("report_evaluations")

    op.drop_index(
        op.f("ix_evidence_source_id"),
        table_name="evidence",
    )

    op.drop_table("evidence")

    op.drop_index(
        op.f("ix_sources_job_id"),
        table_name="sources",
    )

    op.drop_table("sources")

    op.drop_index(
        op.f("ix_research_tasks_status"),
        table_name="research_tasks",
    )

    op.drop_index(
        op.f("ix_research_tasks_job_id"),
        table_name="research_tasks",
    )

    op.drop_table("research_tasks")

    op.drop_index(
        op.f("ix_reports_job_id"),
        table_name="reports",
    )

    op.drop_table("reports")

    op.drop_index(
        op.f("ix_research_jobs_status"),
        table_name="research_jobs",
    )

    op.drop_table("research_jobs")