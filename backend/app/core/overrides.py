"""Recruiter overrides: moving someone forward against the system's advice. Warn and record, never block.

A recruiter keeps the final say, because the model is only tested on synthetic data and a failed rule can be out
of date (a certificate earned but not yet listed). Moving forward someone who failed an eligibility rule needs a
short written reason; an eligible candidate below the decision threshold is flagged and logged, without one.
"""
from dataclasses import dataclass
from typing import Literal

# Moves that take an application further towards a hire. Rejecting someone is never an override.
FORWARD_STATUSES = frozenset({"reviewing", "shortlisted", "interviewed", "hired"})
MIN_REASON_LENGTH = 10
MAX_REASON_LENGTH = 500

OverrideKind = Literal["hard_rule", "below_threshold"]


@dataclass(frozen=True)
class OverrideCheck:
    kind: OverrideKind | None
    final_score: float | None
    hard_rule_passed: bool | None
    rule_reasons: tuple[str, ...]
    threshold: float

    @property
    def needs_reason(self) -> bool:
        return self.kind == "hard_rule"


def check_override(match, threshold: float) -> OverrideCheck:
    """Classify a move against the applicant's latest saved match result (None when they were not evaluated)."""
    if match is None:
        return OverrideCheck(None, None, None, (), threshold)
    score = match.final_weighted_score
    reasons = tuple((match.skill_gap_breakdown or {}).get("rule_reasons") or ())
    if not match.hard_rule_passed:
        kind: OverrideKind | None = "hard_rule"
    elif score is not None and score < threshold:
        kind = "below_threshold"
    else:
        kind = None
    return OverrideCheck(kind, score, match.hard_rule_passed, reasons, threshold)


def clean_reason(reason: str | None) -> str | None:
    text = " ".join((reason or "").split())
    return text or None


def missing_reason(checks: dict, reason: str | None) -> list:
    """Keys whose check needs a reason when none, or too short a one, was given."""
    text = clean_reason(reason)
    if text is not None and len(text) >= MIN_REASON_LENGTH:
        return []
    return [key for key, check in checks.items() if check.needs_reason]


def audit_details(status: str, check: OverrideCheck | None, reason: str | None) -> dict:
    """What the activity log keeps for a status change: the score and rule result behind it, and any override."""
    details: dict = {"status": status}
    if check is None or status not in FORWARD_STATUSES:
        return details
    details.update(final_score=check.final_score, hard_rule_passed=check.hard_rule_passed, threshold=check.threshold)
    if check.rule_reasons:
        details["rule_reasons"] = list(check.rule_reasons)
    if check.kind is not None:
        details["override"] = check.kind
        text = clean_reason(reason)
        if text is not None:
            details["override_reason"] = text
    return details
