"""add candidate opportunity activity

Revision ID: 20260924_0004
Revises: 20260924_0003
Create Date: 2026-09-24
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260924_0004"
down_revision: str | None = "20260924_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    opportunity_status = postgresql.ENUM("saved", "applied", "viewed", name="opportunity_status")
    opportunity_status.create(op.get_bind(), checkfirst=True)
    opportunity_status_column = postgresql.ENUM("saved", "applied", "viewed", name="opportunity_status", create_type=False)
    op.create_table(
        "candidate_opportunities",
        sa.Column("activity_id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", opportunity_status_column, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.candidate_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["job_postings.job_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("activity_id"),
        sa.UniqueConstraint("candidate_id", "job_id", name="uq_candidate_opportunity"),
    )


def downgrade() -> None:
    op.drop_table("candidate_opportunities")
    sa.Enum(name="opportunity_status").drop(op.get_bind(), checkfirst=True)