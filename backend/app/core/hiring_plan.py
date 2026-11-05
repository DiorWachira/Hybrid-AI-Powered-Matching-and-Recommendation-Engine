"""Decide what a simulated hiring run does. Pure logic, so the outcome can be tested without a database."""
from dataclasses import dataclass
from uuid import UUID

# Stages a person can still move on from. Rejected, hired and withdrawn applications are finished.
ACTIVE_STATUSES = frozenset({"submitted", "reviewing", "shortlisted", "interviewed"})


@dataclass(frozen=True)
class RankedApplicant:
    application_id: UUID
    name: str
    status: str
    score: float | None  # None: applied after the latest evaluation, so there is no score to rank on.
    hard_rule_passed: bool | None


@dataclass(frozen=True)
class SimulationPlan:
    selected: tuple[RankedApplicant, ...]
    interviewed: tuple[RankedApplicant, ...]
    hired: RankedApplicant
    rejected: tuple[RankedApplicant, ...]


def rank_eligible(applicants: list[RankedApplicant]) -> list[RankedApplicant]:
    """Active applicants who passed the hard rules, best score first. The id makes ties repeatable."""
    eligible = [item for item in applicants if item.status in ACTIVE_STATUSES and item.hard_rule_passed and item.score is not None]
    return sorted(eligible, key=lambda item: (-item.score, str(item.application_id)))


def plan_simulation(applicants: list[RankedApplicant], top_n: int, interview_count: int) -> SimulationPlan | None:
    """Top N move on, the best of those interview, and the highest match score is hired. None if nobody qualifies."""
    ranked = rank_eligible(applicants)
    if not ranked:
        return None
    selected = ranked[:top_n]
    interviewed = selected[:interview_count]
    hired = interviewed[0]
    rejected = tuple(item for item in applicants if item.status in ACTIVE_STATUSES and item.application_id != hired.application_id)
    return SimulationPlan(selected=tuple(selected), interviewed=tuple(interviewed), hired=hired, rejected=rejected)
