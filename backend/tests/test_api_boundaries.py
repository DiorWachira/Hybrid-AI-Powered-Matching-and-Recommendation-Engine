from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import UUID, uuid4
from datetime import UTC, datetime

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
    ("patch", "/api/jobs/{job_id}/status", {"status": "closed"}),
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


def test_candidate_cannot_list_recruiter_postings(api_client):
    client, database, user = api_client
    user.role = UserRole.candidate
    assert client.get("/api/jobs/mine").status_code == 403
    database.scalars.assert_not_called()


def test_job_list_is_owner_filtered_and_validates_pagination(api_client):
    client, database, user = api_client
    database.scalars.return_value = []
    assert client.get("/api/jobs/mine?limit=6&offset=5").status_code == 200
    statement = database.scalars.call_args.args[0]
    assert statement.whereclause.compare(Employer.user_id == user.user_id)
    assert client.get("/api/jobs/mine?limit=101").status_code == 422
    assert client.get("/api/jobs/mine?offset=-1").status_code == 422


def test_saved_job_results_reject_other_employer(api_client):
    client, database, user = api_client
    database.get.side_effect = [SimpleNamespace(employer_id=uuid4()), SimpleNamespace(user_id=uuid4())]
    assert client.get(f"/api/matches/jobs/{uuid4()}").status_code == 403
    database.execute.assert_not_called()


def test_saved_results_do_not_score_or_write(api_client, monkeypatch):
    from app.api import matches
    client, database, user = api_client
    job_id = uuid4()
    now = datetime.now(UTC)
    database.get.side_effect = [SimpleNamespace(employer_id=uuid4()), SimpleNamespace(user_id=user.user_id)]
    database.scalar.return_value = SimpleNamespace(created_at=now)
    result = MatchResult(match_id=uuid4(), candidate_id=uuid4(), job_id=job_id, hard_rule_passed=True, similarity_score=0.7, growth_score=0.5, skill_overlap_score=0.5, final_weighted_score=0.6, skill_gap_breakdown={"matched_skills": ["SQL"], "missing_skills": ["Python"], "rule_reasons": []}, model_version="test")
    database.execute.return_value.all.return_value = [(result, "Test Candidate")]
    scorer = MagicMock(side_effect=AssertionError("Saved reads must not score"))
    monkeypatch.setattr(matches, "_score_candidate", scorer)
    response = client.get(f"/api/matches/jobs/{job_id}")
    assert response.status_code == 200
    assert response.json()["candidates"][0]["matched_skills"] == ["SQL"]
    assert response.json()["candidates"][0]["missing_skills"] == ["Python"]
    scorer.assert_not_called()
    database.commit.assert_not_called()


def test_unevaluated_job_returns_empty_read_only_result(api_client):
    client, database, user = api_client
    database.get.side_effect = [SimpleNamespace(employer_id=uuid4()), SimpleNamespace(user_id=user.user_id)]
    database.scalar.return_value = None
    response = client.get(f"/api/matches/jobs/{uuid4()}")
    assert response.status_code == 200
    assert response.json()["evaluated_at"] is None
    assert response.json()["candidates"] == []
    database.execute.assert_not_called()
    database.commit.assert_not_called()


@pytest.mark.parametrize("role", [UserRole.candidate, UserRole.recruiter])
def test_match_graph_checks_owner_before_querying_neo4j(api_client, monkeypatch, role):
    from app.api import matches
    client, database, user = api_client
    user.role = role
    records = {MatchResult: SimpleNamespace(candidate_id=uuid4(), job_id=uuid4()), Candidate: SimpleNamespace(user_id=uuid4()), JobPosting: SimpleNamespace(employer_id=uuid4()), Employer: SimpleNamespace(user_id=uuid4())}
    database.get.side_effect = lambda model, identifier: records[model]
    driver = MagicMock(side_effect=AssertionError("Graph must not be queried for unauthorized users"))
    monkeypatch.setattr(matches, "get_neo4j_driver", driver)
    assert client.get(f"/api/matches/{uuid4()}/graph").status_code == 403
    driver.assert_not_called()


def test_evaluation_uses_candidate_id_to_break_score_ties(api_client, monkeypatch):
    from app.api import matches
    from app.schemas import MatchCandidateResponse
    client, database, user = api_client
    job_id = uuid4()
    database.get.side_effect = [SimpleNamespace(job_id=job_id, employer_id=uuid4(), required_skills=[]), SimpleNamespace(user_id=user.user_id)]
    database.scalars.return_value = [SimpleNamespace(candidate_id=UUID(int=index), skills=[]) for index in (2, 1)]
    monkeypatch.setattr(matches, "_score_candidate", lambda candidate, job: MatchCandidateResponse(candidate_id=candidate.candidate_id, full_name="Test", hard_rule_passed=False, rule_reasons=[], skill_overlap=0, semantic_score=0, growth_score=0, final_score=0))
    response = client.post(f"/api/matches/evaluate/{job_id}")
    assert response.status_code == 200
    assert [item["candidate_id"] for item in response.json()["candidates"]] == [str(UUID(int=1)), str(UUID(int=2))]