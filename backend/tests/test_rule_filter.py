from decimal import Decimal

from app.core.rule_filter import CandidateRuleData, JobRuleData, RuleBasedMatcher


def job() -> JobRuleData:
    return JobRuleData(
        required_experience_years=5,
        location="Nairobi",
        salary_range_max=Decimal("250000"),
        mandatory_certifications=frozenset({"AWS Certified Cloud Practitioner"}),
    )


def test_hard_filter_passes_eligible_candidate() -> None:
    candidate = CandidateRuleData(
        years_experience=6,
        location="nairobi",
        expected_salary=Decimal("210000"),
        certifications=frozenset({"AWS Certified Cloud Practitioner"}),
    )
    result = RuleBasedMatcher().check_hard_filters(candidate, job())
    assert result.passed is True
    assert result.reasons == ()


def test_hard_filter_returns_all_failed_constraints() -> None:
    candidate = CandidateRuleData(
        years_experience=2,
        location="Mombasa",
        expected_salary=Decimal("300000"),
        certifications=frozenset(),
    )
    result = RuleBasedMatcher().check_hard_filters(candidate, job())
    assert result.passed is False
    assert result.reasons == (
        "minimum experience not met",
        "location incompatible",
        "salary expectation exceeds job ceiling",
        "mandatory certifications missing: AWS Certified Cloud Practitioner",
    )
