"""enforce profile cardinality and add job posted timestamp

Revision ID: 20260924_0002
Revises: 20260916_0001
Create Date: 2026-09-24
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260924_0002"
down_revision: str | None = "20260916_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint("uq_candidates_user_id", "candidates", ["user_id"])
    op.create_unique_constraint("uq_employers_user_id", "employers", ["user_id"])
    op.add_column(
        "job_postings",
        sa.Column("posted_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("job_postings", "posted_at")
    op.drop_constraint("uq_employers_user_id", "employers", type_="unique")
    op.drop_constraint("uq_candidates_user_id", "candidates", type_="unique")
