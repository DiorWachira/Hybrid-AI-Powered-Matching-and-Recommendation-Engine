from unittest.mock import patch
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import postgresql

from app.api.matches import _score_candidate
from app.db.models import Candidate, JobApplication, JobPosting, MatchResult
from app.schemas import JobCreateRequest


@pytest.mark.parametrize("authorization", [None, False])
def test_authorization_gate_runs_before_ml(authorization):
    candidate = Candidate(candidate_id=uuid4(), full_name="Test", years_experience=4, work_authorized=authorization)
    job = JobPosting(required_experience_years=1, requires_work_authorization=True)
    with patch("app.api.matches.semantic_similarity") as semantic:
        result = _score_candidate(candidate, job)
    assert not result.hard_rule_passed
    assert result.rule_reasons == ["work authorization not confirmed"]
    semantic.assert_not_called()


def test_salary_bounds_rejected_before_database():
    with pytest.raises(ValidationError, match="salary_range_min"):
        JobCreateRequest(title="Analyst", description="A sufficiently long job description", salary_range_min=200, salary_range_max=100)


def test_application_unique_pair_and_match_status_are_database_enforced():
    application_ddl = str(CreateTable(JobApplication.__table__).compile(dialect=postgresql.dialect()))
    match_ddl = str(CreateTable(MatchResult.__table__).compile(dialect=postgresql.dialect()))
    assert "uq_application_candidate_job UNIQUE (candidate_id, job_id)" in application_ddl
    assert "ck_application_status CHECK" in application_ddl
    assert "GENERATED ALWAYS AS" in match_ddl