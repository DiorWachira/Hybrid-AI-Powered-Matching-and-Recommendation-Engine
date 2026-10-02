"""Add application workflow, eligibility fields and durable graph synchronization."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261002_0005"
down_revision = "20260924_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("candidates", sa.Column("work_authorized", sa.Boolean(), nullable=True))
    op.add_column("job_postings", sa.Column("salary_range_min", sa.Numeric(12, 2), nullable=True))
    op.add_column("job_postings", sa.Column("requires_work_authorization", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("match_results", sa.Column("skill_overlap_score", sa.Float(), nullable=True))
    op.add_column("match_results", sa.Column("model_version", sa.String(120), nullable=True))
    op.add_column("match_results", sa.Column("matching_status", sa.String(16), sa.Computed("CASE WHEN hard_rule_passed THEN 'eligible' ELSE 'filtered' END", persisted=True), nullable=False))
    for table, name, condition in [
        ("candidates", "ck_candidate_experience", "years_experience >= 0"),
        ("candidates", "ck_candidate_salary", "expected_salary >= 0"),
        ("job_postings", "ck_job_experience", "required_experience_years >= 0"),
        ("job_postings", "ck_job_salary_nonnegative", "salary_range_min >= 0 AND salary_range_max >= 0"),
        ("job_postings", "ck_job_salary_order", "salary_range_min <= salary_range_max"),
        ("match_results", "ck_match_score", "final_weighted_score BETWEEN 0 AND 1"),
    ]:
        op.create_check_constraint(name, table, condition)
    op.create_index("ix_job_employer", "job_postings", ["employer_id"])
    op.create_index("ix_job_status_posted", "job_postings", ["status", "posted_at"])
    op.create_index("ix_match_candidate_created", "match_results", ["candidate_id", "created_at"])
    op.create_index("ix_match_job_score", "match_results", ["job_id", "final_weighted_score"])
    op.create_table(
        "job_applications",
        sa.Column("application_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("candidates.candidate_id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("job_postings.job_id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(16), server_default="submitted", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint("candidate_id", "job_id", name="uq_application_candidate_job"),
        sa.CheckConstraint("status IN ('submitted', 'reviewing', 'shortlisted', 'rejected', 'hired', 'withdrawn')", name="ck_application_status"),
    )
    op.create_index("ix_application_job_status", "job_applications", ["job_id", "status"])
    op.execute("INSERT INTO job_applications (candidate_id, job_id, created_at, updated_at) SELECT candidate_id, job_id, created_at, updated_at FROM candidate_opportunities WHERE status = 'applied'")
    op.create_table(
        "graph_sync_events",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("entity_type", sa.String(16), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("entity_type IN ('candidate', 'job', 'application')", name="ck_graph_sync_entity"),
    )
    op.create_index("ix_graph_sync_created", "graph_sync_events", ["created_at"])
    op.execute("""
        CREATE FUNCTION enqueue_graph_sync() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE entity_uuid uuid;
        BEGIN
            IF TG_OP = 'DELETE' THEN
                entity_uuid := (to_jsonb(OLD) ->> TG_ARGV[1])::uuid;
            ELSE
                entity_uuid := (to_jsonb(NEW) ->> TG_ARGV[1])::uuid;
            END IF;
            INSERT INTO graph_sync_events(entity_type, entity_id) VALUES (TG_ARGV[0], entity_uuid);
            RETURN NULL;
        END;
        $$
    """)
    for table, entity_type, key in [("candidates", "candidate", "candidate_id"), ("job_postings", "job", "job_id"), ("job_applications", "application", "application_id")]:
        op.execute(f"CREATE TRIGGER {table}_graph_sync AFTER INSERT OR UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION enqueue_graph_sync('{entity_type}', '{key}')")
        op.execute(f"INSERT INTO graph_sync_events(entity_type, entity_id) SELECT '{entity_type}', {key} FROM {table}")
    op.execute("""
        CREATE FUNCTION refresh_updated_at() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN NEW.updated_at := CURRENT_TIMESTAMP; RETURN NEW; END;
        $$
    """)
    for table in ("candidate_opportunities", "job_applications"):
        op.execute(f"CREATE TRIGGER {table}_updated_at BEFORE UPDATE ON {table} FOR EACH ROW EXECUTE FUNCTION refresh_updated_at()")
    op.execute("""
        CREATE FUNCTION enqueue_employer_jobs() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            INSERT INTO graph_sync_events(entity_type, entity_id)
            SELECT 'job', job_id FROM job_postings WHERE employer_id = NEW.employer_id;
            RETURN NULL;
        END;
        $$
    """)
    op.execute("CREATE TRIGGER employer_graph_sync AFTER UPDATE OF industry ON employers FOR EACH ROW EXECUTE FUNCTION enqueue_employer_jobs()")


def downgrade() -> None:
    op.execute("DROP TRIGGER employer_graph_sync ON employers")
    op.execute("DROP FUNCTION enqueue_employer_jobs()")
    for table in ("candidate_opportunities", "job_applications"):
        op.execute(f"DROP TRIGGER {table}_updated_at ON {table}")
    op.execute("DROP FUNCTION refresh_updated_at()")
    for table in ("candidates", "job_postings", "job_applications"):
        op.execute(f"DROP TRIGGER {table}_graph_sync ON {table}")
    op.execute("DROP FUNCTION enqueue_graph_sync()")
    op.drop_table("graph_sync_events")
    op.drop_table("job_applications")
    for table, name in [("candidates", "ck_candidate_experience"), ("candidates", "ck_candidate_salary"), ("job_postings", "ck_job_experience"), ("job_postings", "ck_job_salary_nonnegative"), ("job_postings", "ck_job_salary_order"), ("match_results", "ck_match_score")]:
        op.drop_constraint(name, table, type_="check")
    for table, name in [("job_postings", "ix_job_employer"), ("job_postings", "ix_job_status_posted"), ("match_results", "ix_match_candidate_created"), ("match_results", "ix_match_job_score")]:
        op.drop_index(name, table_name=table)
    for table, column in [("candidates", "work_authorized"), ("job_postings", "salary_range_min"), ("job_postings", "requires_work_authorization"), ("match_results", "skill_overlap_score"), ("match_results", "model_version"), ("match_results", "matching_status")]:
        op.drop_column(table, column)