from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.hiring_plan import RankedApplicant, plan_simulation, rank_eligible
from app.db.models import JobPosting, UserRole
from app.db.postgres import get_db
from app.main import app


def _person(name, score, status="submitted", passed=True):
    return RankedApplicant(uuid4(), name, status, score, passed)


def test_ranking_skips_finished_ineligible_and_unscored_applicants():
    keep = [_person("low", 0.2), _person("high", 0.9, "reviewing")]
    skipped = [_person("failed rules", 0.99, passed=False), _person("no score", None, passed=None), _person("rejected", 0.98, "rejected"), _person("left", 0.97, "withdrawn")]
    assert [item.name for item in rank_eligible(keep + skipped)] == ["high", "low"]


def test_plan_narrows_top_n_to_interviews_to_the_best_score():
    people = [_person(name, score) for name, score in [("e", 0.1), ("a", 0.9), ("c", 0.7), ("b", 0.8), ("d", 0.6)]]
    plan = plan_simulation(people, top_n=4, interview_count=2)
    assert [item.name for item in plan.selected] == ["a", "b", "c", "d"]
    assert [item.name for item in plan.interviewed] == ["a", "b"]
    assert plan.hired.name == "a"
    assert sorted(item.name for item in plan.rejected) == ["b", "c", "d", "e"]


def test_plan_handles_small_pools_and_nobody_eligible():
    only = _person("only", 0.4)
    plan = plan_simulation([only], top_n=5, interview_count=3)
    assert plan.hired == only and plan.selected == (only,) and plan.rejected == ()
    assert plan_simulation([_person("failed", 0.9, passed=False)], top_n=5, interview_count=3) is None


def test_plan_leaves_finished_applicants_alone():
    finished = _person("withdrawn", None, "withdrawn", None)
    plan = plan_simulation([_person("a", 0.9), finished], top_n=5, interview_count=3)
    assert finished not in plan.rejected


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


@pytest.mark.parametrize("method,path,payload", [
    ("get", "/api/jobs/{job_id}/hiring", None),
    ("post", "/api/jobs/{job_id}/hiring/advance", {"application_ids": [str(uuid4())], "status": "reviewing"}),
    ("post", "/api/jobs/{job_id}/hiring/complete", {"close_posting": True}),
    ("post", "/api/jobs/{job_id}/hiring/simulate", {"top_n": 5, "interview_count": 3}),
    ("post", "/api/jobs/{job_id}/hiring/simulate/undo", None),
])
def test_other_recruiters_cannot_touch_a_hiring_flow(api_client, method, path, payload):
    client, database, _ = api_client
    job_id = uuid4()
    job = SimpleNamespace(job_id=job_id, employer_id=uuid4())
    database.get.side_effect = lambda model, identifier: job if model is JobPosting else SimpleNamespace(user_id=uuid4())
    assert client.request(method, path.format(job_id=job_id), json=payload).status_code == 403
    database.commit.assert_not_called()


@pytest.mark.parametrize("role", [UserRole.candidate, UserRole.admin])
def test_hiring_flow_is_recruiter_only(api_client, role):
    client, database, user = api_client
    user.role = role
    assert client.get(f"/api/jobs/{uuid4()}/hiring").status_code == 403
    assert client.get("/api/jobs/mine/filled").status_code == 403
    database.commit.assert_not_called()


def test_advance_rejects_empty_and_invalid_requests(api_client):
    client, _, _ = api_client
    assert client.post(f"/api/jobs/{uuid4()}/hiring/advance", json={"application_ids": [], "status": "reviewing"}).status_code == 422
    assert client.post(f"/api/jobs/{uuid4()}/hiring/advance", json={"application_ids": [str(uuid4())], "status": "submitted"}).status_code == 422
    assert client.post(f"/api/jobs/{uuid4()}/hiring/simulate", json={"top_n": 0}).status_code == 422
