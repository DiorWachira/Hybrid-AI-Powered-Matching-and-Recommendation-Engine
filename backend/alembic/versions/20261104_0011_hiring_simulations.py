"""Record simulated hiring runs so they can be labelled and undone."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261104_0011"
down_revision = "20261026_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hiring_simulations",
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("job_postings.job_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.user_id", ondelete="SET NULL")),
        sa.Column("hired_application_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("job_applications.application_id", ondelete="SET NULL")),
        sa.Column("previous_job_status", sa.String(16), nullable=False),
        sa.Column("previous_statuses", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("hiring_simulations")
