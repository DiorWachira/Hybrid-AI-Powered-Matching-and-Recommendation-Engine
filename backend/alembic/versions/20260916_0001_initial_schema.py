"""initial relational schema

Revision ID: 20260916_0001
Revises:
Create Date: 2026-09-16
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260916_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

user_role = postgresql.ENUM("candidate", "recruiter", "admin", name="user_role")
job_status = postgresql.ENUM("open", "closed", name="job_status")


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
    user_role.create(op.get_bind(), checkfirst=True)
    job_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("user_id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "candidates",
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("location", sa.String(length=120), nullable=True),
        sa.Column("years_experience", sa.Integer(), server_default="0", nullable=False),
        sa.Column("current_salary", sa.Numeric(12, 2), nullable=True),
        sa.Column("expected_salary", sa.Numeric(12, 2), nullable=True),
        sa.Column("parsed_resume_text", sa.Text(), nullable=True),
        sa.Column("embedding_vector", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("candidate_id"),
    )

    op.create_table(
        "employers",
        sa.Column("employer_id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("industry", sa.String(length=120), nullable=True),
        sa.Column("location", sa.String(length=120), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("employer_id"),
    )

    op.create_table(
        "job_postings",
        sa.Column("job_id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("employer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("required_experience_years", sa.Integer(), server_default="0", nullable=False),
        sa.Column("salary_range_max", sa.Numeric(12, 2), nullable=True),
        sa.Column("location", sa.String(length=120), nullable=True),
        sa.Column("mandatory_certifications", postgresql.ARRAY(sa.String(length=120)), nullable=True),
        sa.Column("embedding_vector", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", job_status, server_default="open", nullable=False),
        sa.ForeignKeyConstraint(["employer_id"], ["employers.employer_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("job_id"),
    )

    op.create_table(
        "match_results",
        sa.Column("match_id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("hard_rule_passed", sa.Boolean(), nullable=False),
        sa.Column("similarity_score", sa.Float(), nullable=True),
        sa.Column("growth_score", sa.Float(), nullable=True),
        sa.Column("final_weighted_score", sa.Float(), nullable=True),
        sa.Column("skill_gap_breakdown", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.candidate_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["job_postings.job_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("match_id"),
    )
    op.create_index("ix_match_results_job_id", "match_results", ["job_id"])
    op.create_index("ix_match_results_candidate_id", "match_results", ["candidate_id"])


def downgrade() -> None:
    op.drop_index("ix_match_results_candidate_id", table_name="match_results")
    op.drop_index("ix_match_results_job_id", table_name="match_results")
    op.drop_table("match_results")
    op.drop_table("job_postings")
    op.drop_table("employers")
    op.drop_table("candidates")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    job_status.drop(op.get_bind(), checkfirst=True)
    user_role.drop(op.get_bind(), checkfirst=True)
