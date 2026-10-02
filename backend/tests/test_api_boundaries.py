from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api import candidates, jobs
from app.db.models import Candidate, Employer, JobPosting, JobStatus, MatchResult, UserRole
from app.db.postgres import get_db
from app.main import app


@pytest.fixture
def api_client():
    database = MagicMock(spec=Session)
    user = SimpleNamespace(user_id=uuid4(), role=UserRole.recruiter)
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: database
    app.dependency_overrides[get_current_user] = lambda: user
    with TestClient(app) as client:
        yield client, database, user
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)


def test_recruiter_cannot_evaluate_another_employers_job(api_client):
    client, database, user = api_client
    job = SimpleNamespace(job_id=uuid4(), employer_id=uuid4(), status=JobStatus.open, required_skills=[])
    employer = SimpleNamespace(user_id=uuid4())
    database.get.side_effect = lambda model, identifier: job if model is JobPosting else employer
    database.scalars.return_value = []
    response = client.post(f"/api/matches/evaluate/{job.job_id}")
    assert response.status_code == 403
    database.scalars.assert_not_called()
    database.commit.assert_not_called()


@pytest.mark.parametrize("role", [UserRole.candidate, UserRole.recruiter])
def test_non_admin_cannot_access_overview(api_client, role):
    client, database, user = api_client
    user.role = role
    assert client.get("/api/admin/overview").status_code == 403
    database.scalar.assert_not_called()


def test_invalid_match_job_id_is_validation_error(api_client):
    client, database, user = api_client
    response = client.post("/api/matches/evaluate/not-a-uuid")
    assert response.status_code == 422
    database.get.assert_not_called()


@pytest.mark.parametrize("role", [UserRole.recruiter, UserRole.admin])
def test_owner_and_admin_can_evaluate_job(api_client, role):
    client, database, user = api_client
    user.role = role
    job = SimpleNamespace(job_id=uuid4(), employer_id=uuid4(), status=JobStatus.open, required_skills=[])
    employer = SimpleNamespace(user_id=user.user_id)
    database.get.side_effect = lambda model, identifier: job if model is JobPosting else employer
    database.scalars.return_value = []
    response = client.post(f"/api/matches/evaluate/{job.job_id}")
    assert response.status_code == 200
    database.commit.assert_called_once()


@pytest.mark.parametrize("eligible_ids", [[], [1]])
def test_for_you_excludes_hard_rule_failures(api_client, monkeypatch, eligible_ids):
    client, database, user = api_client
    user.role = UserRole.candidate
    postings = [JobPosting(
        job_id=uuid4(), employer_id=uuid4(), title=f"Role {index}",
        description="A sample role", required_experience_years=1,
        status=JobStatus.open,
    ) for index in range(2)]
    allowed = {postings[index].job_id for index in eligible_ids}
    database.scalar.return_value = SimpleNamespace(candidate_id=uuid4())
    database.scalars.side_effect = [postings, [], []]
    monkeypatch.setattr(candidates, "_score_candidate", lambda candidate, job: SimpleNamespace(
        hard_rule_passed=job.job_id in allowed, final_score=0.0,
    ))
    response = client.get("/api/candidates/dashboard")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["available_opportunities"]) == 2
    assert {entry["job_id"] for entry in payload["for_you"]} == {str(identifier) for identifier in allowed}


def test_open_job_listing_filters_query(api_client):
    client, database, user = api_client
    database.scalars.return_value = []
    assert jobs.list_open_jobs(database) == []
    statement = database.scalars.call_args.args[0]
    assert statement.whereclause.compare(JobPosting.status == JobStatus.open)


@pytest.mark.parametrize("method,path,payload", [
    ("get", "/api/jobs/{job_id}/applications", None),
    ("put", "/api/jobs/{job_id}", {"title": "Analyst", "description": "A sufficiently detailed job description"}),
    ("patch", "/api/jobs/{job_id}/applications/{application_id}", {"status": "reviewing"}),
])
def test_other_employer_cannot_manage_job_or_applications(api_client, method, path, payload):
    client, database, user = api_client
    job_id = uuid4()
    job = SimpleNamespace(job_id=job_id, employer_id=uuid4())
    database.get.side_effect = lambda model, identifier: job if model is JobPosting else SimpleNamespace(user_id=uuid4())
    response = client.request(method, path.format(job_id=job_id, application_id=uuid4()), json=payload)
    assert response.status_code == 403
    database.commit.assert_not_called()


@pytest.mark.parametrize("role", [UserRole.candidate, UserRole.recruiter])
def test_stored_match_is_owner_scoped(api_client, role):
    client, database, user = api_client
    user.role = role
    records = {
        MatchResult: SimpleNamespace(candidate_id=uuid4(), job_id=uuid4()),
        Candidate: SimpleNamespace(user_id=uuid4()),
        JobPosting: SimpleNamespace(employer_id=uuid4()),
        Employer: SimpleNamespace(user_id=uuid4()),
    }
    database.get.side_effect = lambda model, identifier: records[model]
    assert client.get(f"/api/matches/{uuid4()}").status_code == 403


def test_terminal_application_status_cannot_be_reopened(api_client):
    client, database, user = api_client
    database.get.side_effect = lambda model, identifier: SimpleNamespace(employer_id=uuid4()) if model is JobPosting else SimpleNamespace(user_id=user.user_id)
    database.scalar.return_value = SimpleNamespace(status="hired")
    response = client.patch(f"/api/jobs/{uuid4()}/applications/{uuid4()}", json={"status": "reviewing"})
    assert response.status_code == 409
    database.commit.assert_not_called()