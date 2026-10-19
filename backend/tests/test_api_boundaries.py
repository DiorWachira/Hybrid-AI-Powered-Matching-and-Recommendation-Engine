from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import UUID, uuid4
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy.dialects import postgresql

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
def test_simulation_is_admin_only(api_client, monkeypatch, role):
    from app.api import simulation
    client, database, user = api_client
    user.role = role
    build = MagicMock()
    monkeypatch.setattr(simulation, "build_simulation", build)
    assert client.post("/api/admin/simulation").status_code == 403
    build.assert_not_called()
    database.commit.assert_not_called()


def test_simulation_uses_rules_and_model_without_live_database_writes(api_client, monkeypatch):
    from app.api import matches
    client, database, user = api_client
    user.role = UserRole.admin
    monkeypatch.setattr(matches, "semantic_similarity", lambda candidate, job: 0.8)
    response = client.post("/api/admin/simulation")
    assert response.status_code == 200
    result = response.json()
    assert result["sandbox"] is True
    assert result["model_version"] == "2026-10-09-epoch-combiner-r001"
    assert len(result["candidates"]) == 6
    assert len(result["jobs"]) == 2
    assert len(result["matches"]) == 6
    assert any(not match["hard_rule_passed"] for match in result["matches"])
    assert any(match["final_score"] > 0 for match in result["matches"])
    assert result["events"][-1]["kind"] == "completed"
    for method in (database.add, database.execute, database.scalars, database.commit):
        method.assert_not_called()


def test_simulation_profiles_are_not_training_records(api_client, monkeypatch):
    import random
    from app.api import matches
    from data_pipeline.generate_synthetic_data import generate_candidate, generate_job
    client, database, user = api_client
    user.role = UserRole.admin
    monkeypatch.setattr(matches, "semantic_similarity", lambda candidate, job: 0.5)
    result = client.post("/api/admin/simulation").json()
    generator = random.Random(42)
    training_candidates = [generate_candidate(generator) for _ in range(800)]
    training_jobs = [generate_job(generator) for _ in range(100)]
    assert not {item["candidate_id"] for item in result["candidates"]} & {item["candidate_id"] for item in training_candidates}
    assert not {item["resume_text"] for item in result["candidates"]} & {item["resume_text"] for item in training_candidates}
    assert not {item["job_id"] for item in result["jobs"]} & {item["job_id"] for item in training_jobs}
    assert not {item["description"] for item in result["jobs"]} & {item["description"] for item in training_jobs}


@pytest.mark.parametrize("role", [UserRole.candidate, UserRole.recruiter])
def test_non_admin_cannot_access_overview(api_client, role):
    client, database, user = api_client
    user.role = role
    assert client.get("/api/admin/overview").status_code == 403
    database.scalar.assert_not_called()


@pytest.mark.parametrize("role", [UserRole.candidate, UserRole.recruiter])
@pytest.mark.parametrize("path", ["/api/admin/jobs", "/api/admin/recruiters", "/api/admin/recruiters/summary"])
def test_all_jobs_oversight_is_admin_only(api_client, role, path):
    client, database, user = api_client
    user.role = role
    response = client.get(path)
    assert response.status_code == 403
    database.execute.assert_not_called()
    database.scalar.assert_not_called()


def test_admin_lists_all_employers_jobs_with_filters_and_applicant_counts(api_client):
    client, database, user = api_client
    user.role = UserRole.admin
    job = SimpleNamespace(
        job_id=uuid4(), posted_at=datetime.now(UTC), title="Reporting Analyst",
        description="Build operational reporting and decision support for teams.",
        location="Nairobi", required_experience_years=2, salary_range_min=50000,
        salary_range_max=100000, requires_work_authorization=True,
        required_skills=["SQL", "Excel"], mandatory_certifications=["CPA"], status=JobStatus.open,
        employer_id=uuid4(),
    )
    database.execute.return_value.all.return_value = [(job, "Independent Employer", "owner@example.com", False, 3)]
    response = client.get("/api/admin/jobs", params={"search": "Reporting", "status": "open", "offset": 5, "limit": 6})
    assert response.status_code == 200
    assert response.json() == [{
        "job_id": str(job.job_id), "posted_at": job.posted_at.isoformat().replace("+00:00", "Z"),
        "title": "Reporting Analyst", "description": job.description, "location": "Nairobi",
        "required_experience_years": 2, "salary_range_max": "100000", "salary_range_min": "50000",
        "requires_work_authorization": True, "required_skills": ["SQL", "Excel"],
        "mandatory_certifications": ["CPA"], "status": "open", "employer_id": str(job.employer_id),
        "company_name": "Independent Employer", "recruiter_email": "owner@example.com",
        "recruiter_active": False, "applicant_count": 3,
    }]
    statement = str(database.execute.call_args.args[0].compile(dialect=postgresql.dialect()))
    assert "ILIKE" in statement
    assert "job_postings.status" in statement
    assert "LIMIT" in statement and "OFFSET" in statement
    assert "EXISTS" not in statement


def test_admin_job_list_filters_by_recruiter_and_attention(api_client):
    client, database, user = api_client
    user.role = UserRole.admin
    database.execute.return_value.all.return_value = []
    employer_id = uuid4()
    response = client.get("/api/admin/jobs", params={"employer_id": str(employer_id), "attention": "true"})
    assert response.status_code == 200
    statement = database.execute.call_args.args[0].compile(dialect=postgresql.dialect())
    sql = str(statement)
    assert "job_postings.employer_id = " in sql
    # Attention = open AND (recruiter suspended OR posted before the cutoff with no applications).
    assert "users.is_active IS false" in sql
    assert "NOT (EXISTS" in sql
    assert employer_id in statement.params.values()


def test_admin_lists_recruiters_with_posting_and_hiring_totals(api_client):
    # Seeded demo accounts use reserved domains such as .local; stored emails must not be re-validated on output.
    client, database, user = api_client
    user.role = UserRole.admin
    employer = SimpleNamespace(employer_id=uuid4(), user_id=uuid4(), company_name="Savannah Analytics", contact_name="Asha Njeri")
    posted = datetime.now(UTC)
    database.execute.return_value.all.return_value = [(employer, "seed-recruiter@jobbridge.local", True, False, 4, 3, 9, 1, 2, posted)]
    response = client.get("/api/admin/recruiters", params={"search": "Savannah", "offset": 5, "limit": 6})
    assert response.status_code == 200
    assert response.json() == [{
        "employer_id": str(employer.employer_id), "user_id": str(employer.user_id),
        "company_name": "Savannah Analytics", "contact_name": "Asha Njeri", "email": "seed-recruiter@jobbridge.local",
        "is_active": True, "is_demo": False, "jobs_total": 4, "jobs_open": 3, "applications_total": 9,
        "hired_total": 1, "stale_open_jobs": 2, "last_posted_at": posted.isoformat().replace("+00:00", "Z"),
    }]
    sql = str(database.execute.call_args.args[0].compile(dialect=postgresql.dialect()))
    assert "ILIKE" in sql
    assert "FILTER (WHERE" in sql
    assert "NULLS LAST" in sql
    assert "LIMIT" in sql and "OFFSET" in sql


def test_admin_oversight_summary_reports_attention_counts(api_client):
    client, database, user = api_client
    user.role = UserRole.admin
    database.scalar.side_effect = [5, 4, 12, 3, 40, 2, 1, 2, 3]
    response = client.get("/api/admin/recruiters/summary")
    assert response.status_code == 200
    assert response.json() == {
        "recruiters_count": 5, "active_recruiters_count": 4, "jobs_open": 12, "jobs_closed": 3,
        "applications_total": 40, "hired_total": 2, "stale_open_jobs": 1, "suspended_open_jobs": 2,
        "attention_jobs": 3, "stale_after_days": 14,
    }


def test_admin_cannot_create_jobs_through_recruiter_endpoint(api_client):
    client, database, user = api_client
    user.role = UserRole.admin
    response = client.post("/api/jobs/create", json={"title": "Example role", "description": "A detailed description of this example role."})
    assert response.status_code == 403
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


def test_job_evaluation_batches_only_hard_rule_eligible_candidates(api_client, monkeypatch):
    from app.api import matches

    client, database, user = api_client
    user.role = UserRole.recruiter
    job = SimpleNamespace(
        job_id=uuid4(), employer_id=uuid4(), status=JobStatus.open,
        title="Analyst", description="A sufficiently detailed analyst job description",
        location="Nairobi", required_experience_years=2, salary_range_max=None,
        requires_work_authorization=False, mandatory_certifications=[], required_skills=["SQL"],
    )
    employer = SimpleNamespace(user_id=user.user_id)
    eligible = SimpleNamespace(
        candidate_id=uuid4(), full_name="Eligible Candidate", years_experience=3,
        location="Nairobi", expected_salary=None, certifications=[], skills=["SQL"],
        parsed_resume_text="Analyst with SQL skills", work_authorized=True,
    )
    filtered = SimpleNamespace(
        candidate_id=uuid4(), full_name="Filtered Candidate", years_experience=0,
        location="Nairobi", expected_salary=None, certifications=[], skills=["SQL"],
        parsed_resume_text="Entry-level analyst", work_authorized=True,
    )
    database.get.side_effect = lambda model, identifier: job if model is JobPosting else employer
    database.scalars.return_value = [eligible, filtered]
    embed = MagicMock(return_value=[0.8])
    monkeypatch.setattr(matches, "semantic_similarities", embed)

    response = client.post(f"/api/matches/evaluate/{job.job_id}")

    assert response.status_code == 200
    embed.assert_called_once_with([eligible.parsed_resume_text], job.description)
    results = {item["candidate_id"]: item for item in response.json()["candidates"]}
    assert results[str(eligible.candidate_id)]["semantic_score"] == 0.8
    assert results[str(filtered.candidate_id)]["hard_rule_passed"] is False
    assert results[str(filtered.candidate_id)]["semantic_score"] == 0


def test_for_you_only_recommends_eligible_roles_above_model_threshold(api_client, monkeypatch):
    client, database, user = api_client
    user.role = UserRole.candidate
    postings = [JobPosting(
        job_id=uuid4(), employer_id=uuid4(), title=f"Role {index}",
        description=f"Sample role {index}", required_experience_years=1,
        status=JobStatus.open,
    ) for index in range(3)]
    recommended, eligible_only, filtered = postings
    database.scalar.return_value = SimpleNamespace(candidate_id=uuid4(), parsed_resume_text="Analyst")
    database.scalars.side_effect = [postings, [], []]
    monkeypatch.setattr(candidates, "_candidate_rule_result", lambda candidate, job: SimpleNamespace(passed=job is not filtered))
    similarities = MagicMock(return_value=[0.9, 0.2])
    monkeypatch.setattr(candidates, "job_similarities", similarities)
    seen = {}

    def score(candidate, job, semantic_score=None):
        seen[job.job_id] = semantic_score
        return SimpleNamespace(hard_rule_passed=job is not filtered, final_score=0.8 if job is recommended else 0.3 if job is eligible_only else 0.0, recommended=job is recommended)

    monkeypatch.setattr(candidates, "_score_candidate", score)
    response = client.get("/api/candidates/dashboard")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["available_opportunities"]) == 3
    assert [entry["job_id"] for entry in payload["for_you"]] == [str(recommended.job_id)]
    assert payload["for_you"][0]["recommended"] is True
    # One encode call covers every eligible role; rule-filtered roles never reach the encoder.
    similarities.assert_called_once_with("Analyst", ["Sample role 0", "Sample role 1"])
    assert seen == {recommended.job_id: 0.9, eligible_only.job_id: 0.2, filtered.job_id: None}


def test_saved_results_mark_recommendations_only_for_the_active_model(api_client, monkeypatch):
    from app.api import matches
    client, database, user = api_client
    user.role = UserRole.admin
    job_id = uuid4()
    database.get.return_value = SimpleNamespace(job_id=job_id, employer_id=uuid4())
    database.scalar.return_value = SimpleNamespace(created_at=datetime.now(UTC))
    monkeypatch.setattr(matches, "_artifact", lambda: {"model_version": "active", "decision_threshold": 0.5})

    def row(score, version, passed=True):
        return (SimpleNamespace(match_id=uuid4(), candidate_id=uuid4(), hard_rule_passed=passed, skill_gap_breakdown={}, skill_overlap_score=0.5, similarity_score=0.5, growth_score=0.5, final_weighted_score=score, model_version=version), "Candidate")

    database.execute.return_value.all.return_value = [row(0.7, "active"), row(0.4, "active"), row(0.9, "older"), row(0.0, "active", passed=False)]
    response = client.get(f"/api/matches/jobs/{job_id}")
    assert response.status_code == 200
    assert [item["recommended"] for item in response.json()["candidates"]] == [True, False, None, False]


def test_open_job_listing_filters_query(api_client):
    client, database, user = api_client
    database.scalars.return_value = []
    assert jobs.list_open_jobs(database) == []
    statement = database.scalars.call_args.args[0]
    assert statement.whereclause.compare(JobPosting.status == JobStatus.open)


@pytest.mark.parametrize("role", [UserRole.recruiter, UserRole.admin])
def test_candidate_browsing_and_unsave_reject_other_roles(api_client, role):
    client, database, user = api_client
    user.role = role
    assert client.get("/api/candidates/opportunities").status_code == 403
    assert client.delete(f"/api/candidates/opportunities/{uuid4()}").status_code == 403
    database.scalar.assert_not_called()


@pytest.mark.parametrize("parameters", ["limit=101", "offset=-1", "minimum_salary=-1", "maximum_experience=61", "sort=invalid", "activity=invalid"])
def test_browsing_validates_filters(api_client, parameters):
    client, database, user = api_client
    user.role = UserRole.candidate
    assert client.get(f"/api/candidates/opportunities?{parameters}").status_code == 422
    database.execute.assert_not_called()


def test_browsing_does_not_score_or_write(api_client, monkeypatch):
    client, database, user = api_client
    user.role = UserRole.candidate
    database.scalar.return_value = SimpleNamespace(candidate_id=uuid4())
    database.execute.return_value.all.return_value = []
    scorer = MagicMock(side_effect=AssertionError("Browsing must not score"))
    monkeypatch.setattr(candidates, "_score_candidate", scorer)
    assert client.get("/api/candidates/opportunities?query=SQL&location=Nairobi&minimum_salary=100&maximum_experience=3&limit=6&offset=5").json() == []
    scorer.assert_not_called()
    database.commit.assert_not_called()


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
    job = SimpleNamespace(job_id=job_id, employer_id=uuid4(), required_skills=[], description="Test role")
    database.get.side_effect = [job, SimpleNamespace(user_id=user.user_id)]
    database.scalars.return_value = [SimpleNamespace(candidate_id=UUID(int=index), skills=[], parsed_resume_text="") for index in (2, 1)]
    monkeypatch.setattr(matches, "_candidate_rule_result", lambda candidate, posting: SimpleNamespace(passed=True))
    monkeypatch.setattr(matches, "semantic_similarities", lambda texts, description: [0.0] * len(texts))
    monkeypatch.setattr(matches, "_score_candidate", lambda candidate, posting, semantic_score=None: MatchCandidateResponse(candidate_id=candidate.candidate_id, full_name="Test", hard_rule_passed=False, rule_reasons=[], skill_overlap=0, semantic_score=0, growth_score=0, final_score=0))
    response = client.post(f"/api/matches/evaluate/{job_id}")
    assert response.status_code == 200
    assert [item["candidate_id"] for item in response.json()["candidates"]] == [str(UUID(int=1)), str(UUID(int=2))]
    assert all(item["model_version"] == "2026-10-09-epoch-combiner-r001" for item in response.json()["candidates"])

def test_v2_evaluation_records_which_related_skill_earned_credit(api_client, monkeypatch):
    from app.api import matches
    from app.core.match_features import CONTRACT_V2
    client, database, user = api_client
    user.role = UserRole.admin
    job = SimpleNamespace(
        job_id=uuid4(), employer_id=uuid4(), status=JobStatus.open, title="Data Engineer",
        description="Build SQL pipelines", location=None, required_experience_years=2, salary_range_max=None,
        requires_work_authorization=False, mandatory_certifications=[], required_skills=["SQL", "Python"],
    )
    candidate = SimpleNamespace(
        candidate_id=uuid4(), full_name="Alias Candidate", years_experience=3, location=None, expected_salary=None,
        certifications=[], skills=["PostgreSQL", "Python"], parsed_resume_text="PostgreSQL and Python", work_authorized=True,
    )
    base = matches._artifact()
    monkeypatch.setattr(matches, "_artifact", lambda: {**base, "feature_contract": CONTRACT_V2})
    monkeypatch.setattr(matches, "semantic_similarities", lambda texts, job_text: [0.7] * len(texts))
    database.get.return_value = job
    database.scalars.return_value = [candidate]
    response = client.post(f"/api/matches/evaluate/{job.job_id}")
    assert response.status_code == 200
    result = response.json()["candidates"][0]
    assert result["skill_overlap"] == 0.95
    assert result["related_skills"] == [{"required": "SQL", "via": "PostgreSQL", "credit": 0.9}]
    assert result["missing_skills"] == ["SQL"]
    stored = next(call.args[0] for call in database.add.call_args_list if isinstance(call.args[0], MatchResult))
    assert stored.skill_gap_breakdown["related_skills"] == result["related_skills"]
