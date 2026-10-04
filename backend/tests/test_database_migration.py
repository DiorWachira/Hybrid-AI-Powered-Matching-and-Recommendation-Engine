import os
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app import config as app_config
from app.api import candidates, matches
from app.db.postgres import get_db
from app.main import app
from app.schemas import MatchCandidateResponse
from app.utils.security import create_access_token, hash_password
from app.db.base import Base
from app.db.graph_sync import ensure_graph_schema, sync_graph_events
from app.db.models import Candidate, Employer, JobApplication, JobPosting, MatchResult, User, UserRole
from app.db.neo4j_db import get_neo4j_driver

pytestmark = pytest.mark.skipif(os.getenv("RUN_DATABASE_MIGRATION_TESTS") != "1", reason="requires local disposable PostgreSQL database privileges and Neo4j")


@pytest.fixture
def migrated_database(monkeypatch):
    settings = app_config.get_settings()
    source_url = make_url(settings.database_url)
    if source_url.host not in {"localhost", "127.0.0.1"}:
        pytest.skip("migration tests only run on local PostgreSQL")
    source_url = source_url.set(host="127.0.0.1").update_query_dict({"connect_timeout": "5"})
    database_name = "jobbridge_test_" + uuid4().hex
    admin = create_engine(source_url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    test_url = source_url.set(database=database_name)
    engine = create_engine(test_url)
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{database_name}"'))
    configuration = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    configuration.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "alembic"))
    monkeypatch.setattr(app_config, "get_settings", lambda: SimpleNamespace(database_url=test_url.render_as_string(hide_password=False)))
    try:
        command.upgrade(configuration, "head")
        yield engine, configuration
    finally:
        engine.dispose()
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE "{database_name}" WITH (FORCE)'))
        admin.dispose()


def test_migration_metadata_constraints_and_roundtrip(migrated_database):
    engine, configuration = migrated_database
    with engine.connect() as connection:
        differences = compare_metadata(MigrationContext.configure(connection), Base.metadata)
        assert differences == []
    with Session(engine) as database:
        candidate_user = User(email="candidate@example.test", password_hash="not-a-login", role=UserRole.candidate)
        employer_user = User(email="recruiter@example.test", password_hash="not-a-login", role=UserRole.recruiter)
        database.add_all([candidate_user, employer_user])
        database.flush()
        candidate = Candidate(user_id=candidate_user.user_id, full_name="Migration Test", years_experience=2)
        employer = Employer(user_id=employer_user.user_id, company_name="Test")
        database.add_all([candidate, employer])
        database.flush()
        job = JobPosting(employer_id=employer.employer_id, title="Test", description="Test role", salary_range_min=100, salary_range_max=200)
        database.add(job)
        database.flush()
        candidate_id, job_id = candidate.candidate_id, job.job_id
        database.add(JobApplication(candidate_id=candidate_id, job_id=job_id))
        database.commit()
        assert database.scalar(text("SELECT count(*) FROM graph_sync_events")) == 3
        database.rollback()
        with pytest.raises(IntegrityError):
            database.add(JobApplication(candidate_id=candidate_id, job_id=job_id))
            database.commit()
        database.rollback()
        with pytest.raises(IntegrityError):
            database.execute(text("UPDATE job_postings SET salary_range_min = 300 WHERE job_id = :id"), {"id": job_id})
        database.rollback()
        database.execute(text("UPDATE candidates SET skills = ARRAY['SQL'] WHERE candidate_id = :id"), {"id": candidate_id})
        database.rollback()
        assert database.scalar(text("SELECT count(*) FROM graph_sync_events")) == 3
    command.downgrade(configuration, "20260924_0004")
    assert "job_applications" not in inspect(engine).get_table_names()
    command.upgrade(configuration, "head")
    with engine.connect() as connection:
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []


def test_graph_projection_update_delete_and_same_title_jobs(migrated_database):
    engine, configuration = migrated_database
    identifiers = [uuid4() for _ in range(4)]
    candidate_id, first_job_id, second_job_id, application_id = identifiers
    skill_name = "test-skill-" + uuid4().hex
    industry = "test-industry-" + uuid4().hex
    with get_neo4j_driver() as driver:
        ensure_graph_schema(driver)
        try:
            with Session(engine) as database:
                candidate_user = User(email="candidate@example.test", password_hash="not-a-login", role=UserRole.candidate)
                employer_user = User(email="employer@example.test", password_hash="not-a-login", role=UserRole.recruiter)
                database.add_all([candidate_user, employer_user])
                database.flush()
                employer = Employer(user_id=employer_user.user_id, company_name="Test", industry=industry)
                database.add(employer)
                database.add(Candidate(candidate_id=candidate_id, user_id=candidate_user.user_id, full_name="Test", skills=[skill_name.upper()]))
                database.flush()
                database.add_all([JobPosting(job_id=identifier, employer_id=employer.employer_id, title="Same title", description="Test", required_skills=[skill_name]) for identifier in (first_job_id, second_job_id)])
                database.flush()
                database.add(JobApplication(application_id=application_id, candidate_id=candidate_id, job_id=first_job_id))
                database.commit()
                assert sync_graph_events(database, driver) == 4
                assert sync_graph_events(database, driver) == 0
                saved = MatchResult(candidate_id=candidate_id, job_id=first_job_id, hard_rule_passed=True)
                database.add(saved)
                database.commit()
                graph_view = matches.read_match_graph(saved.match_id, SimpleNamespace(role=UserRole.admin), database)
                assert graph_view["state"] == "current_projection"
                assert {edge["label"] for edge in graph_view["edges"]} >= {"HAS_SKILL", "REQUIRES_SKILL", "APPLIED_TO"}
                assert len(graph_view["nodes"]) == 3
                database.rollback()
                with driver.session(database="neo4j") as graph:
                    assert graph.run("MATCH (job:Job) WHERE job.id IN $ids RETURN count(job) AS count", ids=[str(first_job_id), str(second_job_id)]).single()["count"] == 2
                    assert graph.run("MATCH (:Candidate {id: $id})-[:HAS_SKILL]->(:Skill {name: $skill}) RETURN count(*) AS count", id=str(candidate_id), skill=skill_name).single()["count"] == 1
                    assert graph.run("MATCH ()-[edge:APPLIED_TO {application_id: $id}]->() RETURN edge.status AS status", id=str(application_id)).single()["status"] == "submitted"
                database.get(Candidate, candidate_id).skills = []
                database.get(JobApplication, application_id).status = "shortlisted"
                database.commit()
                assert sync_graph_events(database, driver) == 2
                with driver.session(database="neo4j") as graph:
                    assert graph.run("MATCH (:Candidate {id: $id})-[:HAS_SKILL]->() RETURN count(*) AS count", id=str(candidate_id)).single()["count"] == 0
                    assert graph.run("MATCH ()-[edge:APPLIED_TO {application_id: $id}]->() RETURN edge.status AS status", id=str(application_id)).single()["status"] == "shortlisted"
                database.delete(database.get(JobPosting, first_job_id))
                database.commit()
                assert sync_graph_events(database, driver) == 2
                with driver.session(database="neo4j") as graph:
                    assert graph.run("MATCH (job:Job {id: $id}) RETURN count(job) AS count", id=str(first_job_id)).single()["count"] == 0
        finally:
            with driver.session(database="neo4j") as graph:
                graph.run("MATCH (node) WHERE node.id IN $ids DETACH DELETE node", ids=[str(identifier) for identifier in identifiers]).consume()
                graph.run("MATCH (node) WHERE node.name IN $names AND NOT (node)--() DELETE node", names=[skill_name, industry]).consume()


def test_authenticated_application_and_match_workflow(migrated_database, monkeypatch):
    engine, configuration = migrated_database

    def database_dependency():
        with Session(engine) as database:
            yield database

    def score(candidate, job):
        return MatchCandidateResponse(candidate_id=candidate.candidate_id, full_name=candidate.full_name, hard_rule_passed=True, rule_reasons=[], skill_overlap=0.8, semantic_score=0.7, growth_score=0.6, final_score=0.75)

    monkeypatch.setattr(candidates, "_score_candidate", score)
    monkeypatch.setattr(matches, "_score_candidate", score)
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = database_dependency
    try:
        with TestClient(app) as client:
            def account(email, role):
                response = client.post("/api/auth/register", json={"email": email, "password": "IsolatedTestOnly123!", "role": role, "full_name": "Test Candidate", "company_name": "Test Employer"})
                assert response.status_code == 201
                login = client.post("/api/auth/login", json={"email": email, "password": "IsolatedTestOnly123!"})
                assert login.status_code == 200
                return {"Authorization": "Bearer " + login.json()["access_token"]}

            candidate_headers = account("candidate@example.org", "candidate")
            recruiter_headers = account("recruiter@example.org", "recruiter")
            other_headers = account("other@example.org", "recruiter")
            job_payload = {"title": "Analyst", "description": "A sufficiently detailed job description", "required_skills": ["SQL"], "salary_range_min": 100, "salary_range_max": 200}
            created = client.post("/api/jobs/create", json=job_payload, headers=recruiter_headers)
            assert created.status_code == 201
            job_id = created.json()["job_id"]
            initial_results = client.get(f"/api/matches/jobs/{job_id}", headers=recruiter_headers)
            assert initial_results.status_code == 200
            assert initial_results.json()["evaluated_at"] is None
            for _ in range(2):
                assert client.post(f"/api/candidates/opportunities/{job_id}", json={"status": "applied"}, headers=candidate_headers).status_code == 200
            applications = client.get("/api/candidates/me/applications", headers=candidate_headers).json()
            assert len(applications) == 1
            application_id = applications[0]["application_id"]
            assert client.get(f"/api/jobs/{job_id}/applications", headers=other_headers).status_code == 403
            updated = client.patch(f"/api/jobs/{job_id}/applications/{application_id}", json={"status": "reviewing"}, headers=recruiter_headers)
            assert updated.status_code == 200
            assert updated.json()["status"] == "reviewing"
            assert updated.json()["updated_at"] >= applications[0]["updated_at"]
            evaluated = client.post(f"/api/matches/evaluate/{job_id}", headers=recruiter_headers)
            assert evaluated.status_code == 200
            match_id = evaluated.json()["candidates"][0]["match_id"]
            assert evaluated.json()["candidates"][0]["missing_skills"] == ["SQL"]
            saved_results = client.get(f"/api/matches/jobs/{job_id}", headers=recruiter_headers)
            assert saved_results.status_code == 200
            assert saved_results.json() == evaluated.json()
            assert client.get(f"/api/matches/jobs/{job_id}", headers=other_headers).status_code == 403
            assert client.get(f"/api/matches/jobs/{job_id}", headers=candidate_headers).status_code == 403
            assert client.get(f"/api/matches/{match_id}", headers=candidate_headers).status_code == 200
            assert client.get(f"/api/matches/{match_id}", headers=other_headers).status_code == 403
            assert client.post(f"/api/matches/evaluate/{job_id}", headers=recruiter_headers).status_code == 200
            latest = client.get(f"/api/matches/jobs/{job_id}", headers=recruiter_headers).json()
            assert len(latest["candidates"]) == 1
            assert latest["candidates"][0]["match_id"] != match_id
            with Session(engine) as database:
                assert database.scalar(text("SELECT count(*) FROM match_results")) == 2
            assert client.get(f"/api/matches/{match_id}", headers=candidate_headers).status_code == 200
            closed = client.put(f"/api/jobs/{job_id}", json={**job_payload, "status": "closed"}, headers=recruiter_headers)
            assert closed.status_code == 200
            assert client.get("/api/jobs/").json() == []
            assert client.post(f"/api/candidates/opportunities/{job_id}", json={"status": "applied"}, headers=candidate_headers).status_code == 409
            with Session(engine) as database:
                admin = User(email="admin@example.org", password_hash=hash_password("TestAdminOnly123!"), role=UserRole.admin)
                database.add(admin)
                database.commit()
                admin_id = admin.user_id
            admin_headers = {"Authorization": "Bearer " + create_access_token(admin_id, "admin")}
            candidate_id = client.get("/api/auth/me", headers=candidate_headers).json()["user_id"]
            assert client.patch(f"/api/admin/users/{candidate_id}", json={"is_active": False}, headers=recruiter_headers).status_code == 403
            assert client.patch(f"/api/admin/users/{candidate_id}", json={"is_active": False}, headers=admin_headers).status_code == 200
            assert client.get("/api/auth/me", headers=candidate_headers).status_code == 403
            empty_run = client.post(f"/api/matches/evaluate/{job_id}", headers=recruiter_headers)
            assert empty_run.status_code == 200
            assert empty_run.json()["candidates"] == []
            assert client.get(f"/api/matches/jobs/{job_id}", headers=recruiter_headers).json() == empty_run.json()
            assert client.post("/api/auth/login", json={"email": "candidate@example.org", "password": "IsolatedTestOnly123!"}).status_code == 403
            assert client.patch(f"/api/admin/users/{admin_id}", json={"is_active": False}, headers=admin_headers).status_code == 409
            assert client.patch(f"/api/admin/users/{candidate_id}", json={"is_active": True}, headers=admin_headers).status_code == 200
            assert client.get("/api/auth/me", headers=candidate_headers).status_code == 200
            overview = client.get("/api/admin/overview", headers=admin_headers)
            assert overview.status_code == 200
            actions = {event["action"] for event in overview.json()["recent_activity"]}
            assert {"account.suspended", "account.reactivated", "application.submitted", "matches.evaluated"} <= actions
            users_response = client.get("/api/admin/users", params={"search": "candidate@example.org"}, headers=admin_headers)
            assert users_response.status_code == 200
            assert len(users_response.json()) == 1
            assert "password_hash" not in users_response.text
            issued = client.post(f"/api/admin/users/{candidate_id}/password-reset", json={"password": "TestAdminOnly123!"}, headers=admin_headers)
            assert issued.status_code == 200
            reset_token = issued.json()["token"]
            invalid = client.post("/api/auth/reset-password", json={"token": "x" * 43, "new_password": "UpdatedPassword123!"})
            assert invalid.status_code == 400
            reset = client.post("/api/auth/reset-password", json={"token": reset_token, "new_password": "UpdatedPassword123!"})
            assert reset.status_code == 200
            assert client.post("/api/auth/reset-password", json={"token": reset_token, "new_password": "UpdatedPassword123!"}).status_code == 400
            assert client.get("/api/auth/me", headers=candidate_headers).status_code == 401
            assert client.post("/api/auth/login", json={"email": "candidate@example.org", "password": "IsolatedTestOnly123!"}).status_code == 401
            assert client.post("/api/auth/login", json={"email": "candidate@example.org", "password": "UpdatedPassword123!"}).status_code == 200
            second = client.post(f"/api/admin/users/{candidate_id}/password-reset", json={"password": "TestAdminOnly123!"}, headers=admin_headers)
            assert second.status_code == 200
            with Session(engine) as database:
                database.execute(text("UPDATE users SET password_reset_expires_at = CURRENT_TIMESTAMP - interval '1 minute' WHERE user_id = :id"), {"id": candidate_id})
                database.commit()
            assert client.post("/api/auth/reset-password", json={"token": second.json()["token"], "new_password": "UpdatedPassword123!"}).status_code == 400
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)