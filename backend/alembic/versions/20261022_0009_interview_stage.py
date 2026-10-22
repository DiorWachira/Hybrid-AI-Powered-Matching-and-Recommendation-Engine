"""Add the interviewed application stage between shortlisting and hiring."""
from alembic import op

revision = "20261022_0009"
down_revision = "20261022_0008"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("ck_application_status", "job_applications", type_="check")
    op.create_check_constraint("ck_application_status", "job_applications", "status IN ('submitted', 'reviewing', 'shortlisted', 'interviewed', 'rejected', 'hired', 'withdrawn')")


def downgrade():
    # Interviewed applications fall back to shortlisted, the stage they came from.
    op.execute("UPDATE job_applications SET status = 'shortlisted' WHERE status = 'interviewed'")
    op.drop_constraint("ck_application_status", "job_applications", type_="check")
    op.create_check_constraint("ck_application_status", "job_applications", "status IN ('submitted', 'reviewing', 'shortlisted', 'rejected', 'hired', 'withdrawn')")
