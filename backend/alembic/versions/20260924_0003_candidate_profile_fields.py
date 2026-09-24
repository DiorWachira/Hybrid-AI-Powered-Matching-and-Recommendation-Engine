"""add structured candidate profile fields

Revision ID: 20260924_0003
Revises: 20260924_0002
Create Date: 2026-09-24
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260924_0003"
down_revision: str | None = "20260924_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("candidates", sa.Column("skills", postgresql.ARRAY(sa.String(length=120)), nullable=True))
    op.add_column("candidates", sa.Column("certifications", postgresql.ARRAY(sa.String(length=120)), nullable=True))
    op.add_column("job_postings", sa.Column("required_skills", postgresql.ARRAY(sa.String(length=120)), nullable=True))


def downgrade() -> None:
    op.drop_column("job_postings", "required_skills")
    op.drop_column("candidates", "certifications")
    op.drop_column("candidates", "skills")