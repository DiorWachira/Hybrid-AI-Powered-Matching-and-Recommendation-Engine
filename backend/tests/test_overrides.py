"""Recruiter overrides: warn and record, never block; a failed eligibility rule needs a reason, enforced on the server."""
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.api import hiring, jobs
from app.api.dependencies import get_current_user
from app.core.overrides import audit_details, check_override, missing_reason
from app.db.models import AuditEvent, Candidate, Employer, HiringSimulation, JobPosting, JobStatus, UserRole
from app.db.postgres import get_db
from app.main import app

THRESHOLD = 0.46


def _match(passed=True, score=0.8, reasons=()):
    return SimpleNamespace(hard_rule_passed=passed, final_weighted_score=score, skill_gap_breakdown={"rule_reasons": list(reasons)})


@pytest.mark.parametrize("match,kind", [
    (None, None),
    (_match(score=0.9), None),
    (_match(score=THRESHOLD), None),
    (_match(score=0.2), "below_threshold"),
    (_match(passed=False, score=0.0, reasons=["location incompatible"]), "hard_rule"),
])
def test_check_classifies_moves_against_the_latest_evaluation(match, kind):
    check = check_override(match, THRESHOLD)
    assert check.kind == kind
    assert check.needs_reason is (kind == "hard_rule")


def test_only_hard_rule_failures_need_a_reason_of_ten_characters():
    checks = {"failed": check_override(_match(passed=False, score=0.0), THRESHOLD), "low": check_override(_match(score=0.1), THRESHOLD)}
    assert missing_reason(checks, None) == ["failed"]
    assert missing_reason(checks, "   long   enough ") == []
    assert missing_reason(checks, "short") == ["failed"]
    assert missing_reason({"low": checks["low"]}, None) == []


def test_audit_details_keep_score_rule_result_and_reason():
    failed = check_override(_match(passed=False, score=0.0, reasons=["minimum experience not met"]), THRESHOLD)
    details = audit_details("hired", failed, "  Earned the certificate   last month ")
    assert details == {"status": "hired", "final_score": 0.0, "hard_rule_passed": False, "threshold": THRESHOLD, "rule_reasons": ["minimum experience not met"], "override": "hard_rule", "override_reason": "Earned the certificate last month"}
    assert audit_details("rejected", failed, "irrelevant reason") == {"status": "rejected"}
    assert "override" not in audit_details("shortlisted", check_override(_match(score=0.9), THRESHOLD), None)
    assert audit_details("reviewing", None, None) == {"status": "reviewing"}


@pytest.fixture
def api_client(monkeypatch):
    database = MagicMock(spec=Session)
    user = SimpleNamespace(user_id=uuid4(), role=UserRole.recruiter)
    job = SimpleNamespace(job_id=uuid4(), employer_id=uuid4(), status=JobStatus.open)
    candidate = SimpleNamespace(candidate_id=uuid4(), full_name="Wanjiru Kamau")
    application = SimpleNamespace(application_id=uuid4(), candidate_id=candidate.candidate_id, job_id=job.job_id, status="interviewed", created_at=datetime.now(UTC), updated_at=datetime.now(UTC))
    records = {JobPosting: job, Employer: SimpleNamespace(user_id=user.user_id), Candidate: candidate, HiringSimulation: None}
    database.get.side_effect = lambda model, identifier: records.get(model)
    database.scalar.return_value = application
    database.scalars.return_value = [application]
    scores = {}
    monkeypatch.setattr(jobs, "latest_scores", lambda db, job_id: (datetime.now(UTC), scores))
    monkeypatch.setattr(hiring, "latest_scores", lambda db, job_id: (datetime.now(UTC), scores))
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: database
    app.dependency_overrides[get_current_user] = lambda: user
    with TestClient(app) as client:
        yield SimpleNamespace(client=client, db=database, job=job, candidate=candidate, application=application, scores=scores)
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)


def _audits(database):
    return [call.args[0] for call in database.add.call_args_list if isinstance(call.args[0], AuditEvent)]


def _single_url(env):
    return f"/api/jobs/{env.job.job_id}/applications/{env.application.application_id}"


def _bulk_url(env):
    return f"/api/jobs/{env.job.job_id}/hiring/advance"


@pytest.mark.parametrize("send", [
    lambda env, reason: env.client.patch(_single_url(env), json={"status": "hired", "override_reason": reason}),
    lambda env, reason: env.client.post(_bulk_url(env), json={"application_ids": [str(env.application.application_id)], "status": "hired", "override_reason": reason}),
], ids=["applicant list", "hiring flow"])
def test_server_refuses_to_advance_a_failed_rule_without_a_reason(api_client, send):
    env = api_client
    env.scores[env.candidate.candidate_id] = _match(passed=False, score=0.0, reasons=["location incompatible"])
    for reason in (None, "", "too short"):
        response = send(env, reason)
        assert response.status_code == 422
        assert "Wanjiru Kamau" in response.json()["detail"]
    env.db.commit.assert_not_called()
    assert env.application.status == "interviewed"

    assert send(env, "Relocating to Nairobi next month, confirmed by phone").status_code == 200
    details = _audits(env.db)[-1].details
    assert details["override"] == "hard_rule"
    assert details["override_reason"] == "Relocating to Nairobi next month, confirmed by phone"
    assert details["rule_reasons"] == ["location incompatible"] and details["hard_rule_passed"] is False


def test_low_score_is_recorded_without_asking_for_a_reason(api_client):
    env = api_client
    env.scores[env.candidate.candidate_id] = _match(score=0.31)
    assert env.client.patch(_single_url(env), json={"status": "hired"}).status_code == 200
    details = _audits(env.db)[-1].details
    assert details == {"status": "hired", "final_score": 0.31, "hard_rule_passed": True, "threshold": details["threshold"], "override": "below_threshold"}


def test_rejecting_or_recommended_moves_are_not_overrides(api_client):
    env = api_client
    env.scores[env.candidate.candidate_id] = _match(passed=False, score=0.0)
    assert env.client.patch(_single_url(env), json={"status": "rejected"}).status_code == 200
    assert _audits(env.db)[-1].details == {"status": "rejected"}
    env.application.status = "interviewed"
    env.scores[env.candidate.candidate_id] = _match(score=0.95)
    assert env.client.patch(_single_url(env), json={"status": "hired"}).status_code == 200
    assert "override" not in _audits(env.db)[-1].details


def test_applicant_list_shows_each_applicants_latest_result(api_client):
    env = api_client
    candidate = SimpleNamespace(candidate_id=env.candidate.candidate_id, full_name="Wanjiru Kamau", location="Nairobi", years_experience=3, skills=["SQL"], certifications=[])
    env.db.execute.return_value.all.return_value = [(env.application, candidate)]
    env.scores[env.candidate.candidate_id] = _match(passed=False, score=0.0, reasons=["minimum experience not met"])
    applicant = env.client.get(f"/api/jobs/{env.job.job_id}/applications").json()[0]
    assert (applicant["hard_rule_passed"], applicant["recommended"], applicant["rule_reasons"]) == (False, False, ["minimum experience not met"])


def test_evaluation_returns_the_model_and_records_the_posting_rules(api_client, monkeypatch):
    from decimal import Decimal

    from app.api import matches
    env = api_client
    posting = SimpleNamespace(
        job_id=env.job.job_id, employer_id=env.job.employer_id, status=JobStatus.open, title="Analyst", description="Analyse data with SQL",
        location="Nairobi", required_experience_years=2, salary_range_max=Decimal("150000"), requires_work_authorization=False,
        mandatory_certifications=["CCNA"], required_skills=["SQL"],
    )
    env.db.get.side_effect = lambda model, identifier: posting if model is JobPosting else SimpleNamespace(user_id=None) if model is Employer else None
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(user_id=uuid4(), role=UserRole.admin)
    env.db.scalars.return_value = []
    monkeypatch.setattr(matches, "semantic_similarities", lambda texts, job_text: [])
    body = env.client.post(f"/api/matches/evaluate/{posting.job_id}").json()
    artifact = matches._artifact()
    assert body["model"]["version"] == artifact["model_version"] and body["model"]["threshold"] == artifact["decision_threshold"]
    assert [item["key"] for item in body["model"]["inputs"]] == ["semantic_score", "skill_overlap", "growth_score"]
    assert [item["weight"] for item in body["model"]["inputs"]] == artifact["logistic_regression"]["coefficients"]
    rules = {item["rule"]: item for item in body["requirements"]}
    assert rules["work_authorization"] == {"rule": "work_authorization", "applied": False, "requirement": None}
    assert rules["experience"]["requirement"] == "At least 2 years" and rules["location"]["requirement"] == "Nairobi"
    assert rules["salary"]["requirement"] == "Up to 150,000" and rules["certifications"]["requirement"] == "CCNA"
    saved = next(event for event in _audits(env.db) if event.action == "matches.evaluated")
    assert saved.details["requirements"] == body["requirements"]


def test_admin_can_filter_the_log_to_overrides(api_client):
    env = api_client
    user = SimpleNamespace(user_id=uuid4(), role=UserRole.admin)
    app.dependency_overrides[get_current_user] = lambda: user
    env.db.execute.return_value.all.return_value = []
    assert env.client.get("/api/admin/activity?overrides=true").status_code == 200
    sql = str(env.db.execute.call_args.args[0].compile(dialect=postgresql.dialect()))
    assert "audit_events.details ?" in sql and "audit_events.action =" in sql
