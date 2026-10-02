"""Add single-use password recovery and session revocation."""
from alembic import op
import sqlalchemy as sa

revision = "20261002_0007"
down_revision = "20261002_0006"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("auth_version", sa.Integer(), server_default="0", nullable=False))
    op.add_column("users", sa.Column("password_reset_hash", sa.String(64), nullable=True))
    op.add_column("users", sa.Column("password_reset_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.create_unique_constraint("uq_users_password_reset_hash", "users", ["password_reset_hash"])


def downgrade():
    op.drop_constraint("uq_users_password_reset_hash", "users", type_="unique")
    op.drop_column("users", "password_reset_expires_at")
    op.drop_column("users", "password_reset_hash")
    op.drop_column("users", "auth_version")