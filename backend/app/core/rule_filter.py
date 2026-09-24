from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class CandidateRuleData:
    years_experience: int
    location: str | None
    expected_salary: Decimal | None
    certifications: frozenset[str]


@dataclass(frozen=True)
class JobRuleData:
    required_experience_years: int
    location: str | None
    salary_range_max: Decimal | None
    mandatory_certifications: frozenset[str]


@dataclass(frozen=True)
class RuleFilterResult:
    passed: bool
    reasons: tuple[str, ...]


class RuleBasedMatcher:
    """Tier 1 gate. A rejected profile must not proceed to graph or ML scoring."""

    def check_hard_filters(self, candidate: CandidateRuleData, job: JobRuleData) -> RuleFilterResult:
        failures: list[str] = []
        if candidate.years_experience < job.required_experience_years:
            failures.append("minimum experience not met")
        if job.location and candidate.location and candidate.location.casefold() != job.location.casefold():
            failures.append("location incompatible")
        if job.salary_range_max is not None and candidate.expected_salary is not None:
            if candidate.expected_salary > job.salary_range_max:
                failures.append("salary expectation exceeds job ceiling")
        missing = job.mandatory_certifications - candidate.certifications
        if missing:
            failures.append("mandatory certifications missing: " + ", ".join(sorted(missing)))
        return RuleFilterResult(passed=not failures, reasons=tuple(failures))
