"""Move seeded demo accounts from @jobbridge.local to @jobbridge.example.org.

email-validator rejects the special-use .local domain, so those accounts could not sign in.
"""
from alembic import op

revision = "20261026_0010"
down_revision = "20261022_0009"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "UPDATE users SET email = replace(email, '@jobbridge.local', '@jobbridge.example.org') "
        "WHERE is_demo AND email LIKE '%@jobbridge.local'"
    )


def downgrade():
    op.execute(
        "UPDATE users SET email = replace(email, '@jobbridge.example.org', '@jobbridge.local') "
        "WHERE is_demo AND (email LIKE 'seed-%@jobbridge.example.org' OR email LIKE 'oversight-%@jobbridge.example.org')"
    )
