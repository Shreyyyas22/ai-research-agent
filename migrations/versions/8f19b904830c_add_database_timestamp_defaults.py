"""add database timestamp defaults

Revision ID: 8f19b904830c
Revises: 6cfe38d6fcf0
Create Date: 2026-10-04 13:20:05.099252

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8f19b904830c"
down_revision: Union[str, Sequence[str], None] = "6cfe38d6fcf0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add database-side timestamp defaults."""

    op.alter_column(
        "research_jobs",
        "created_at",
        server_default=sa.text("NOW()"),
    )

    op.alter_column(
        "research_tasks",
        "created_at",
        server_default=sa.text("NOW()"),
    )

    op.alter_column(
        "sources",
        "created_at",
        server_default=sa.text("NOW()"),
    )

    op.alter_column(
        "evidence",
        "created_at",
        server_default=sa.text("NOW()"),
    )

    op.alter_column(
        "reports",
        "created_at",
        server_default=sa.text("NOW()"),
    )

    op.alter_column(
        "report_evaluations",
        "created_at",
        server_default=sa.text("NOW()"),
    )


def downgrade() -> None:
    """Remove database-side timestamp defaults."""

    op.alter_column(
        "report_evaluations",
        "created_at",
        server_default=None,
    )

    op.alter_column(
        "reports",
        "created_at",
        server_default=None,
    )

    op.alter_column(
        "evidence",
        "created_at",
        server_default=None,
    )

    op.alter_column(
        "sources",
        "created_at",
        server_default=None,
    )

    op.alter_column(
        "research_tasks",
        "created_at",
        server_default=None,
    )

    op.alter_column(
        "research_jobs",
        "created_at",
        server_default=None,
    )