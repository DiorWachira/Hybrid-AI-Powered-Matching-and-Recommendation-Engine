from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.core.rule_filter import CandidateRuleData, JobRuleData, RuleBasedMatcher
from app.db.models import AuditEvent, Candidate, Employer, JobPosting, MatchResult, User, UserRole
from app.core.hybrid_matcher import calibrated_score, semantic_similarity
from app.db.postgres import get_db
from app.schemas import MatchCandidateResponse, MatchEvaluationResponse, StoredMatchResponse

router = APIRouter(prefix="/matches", tags=["matches"])


@router.get("/{match_id}", response_model=StoredMatchResponse)
def read_match(match_id: UUID, user: User = Depends(require_roles(UserRole.candidate, UserRole.recruiter, UserRole.admin)), db: Session = Depends(get_db)):
    result = db.get(MatchResult, match_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Match result not found")
    if user.role == UserRole.candidate:
        candidate = db.get(Candidate, result.candidate_id)
        if candidate is None or candidate.user_id != user.user_id:
            raise HTTPException(status_code=403, detail="This match belongs to another candidate")
    elif user.role == UserRole.recruiter:
        job = db.get(JobPosting, result.job_id)
        employer = db.get(Employer, job.employer_id) if job else None
        if employer is None or employer.user_id != user.user_id:
            raise HTTPException(status_code=403, detail="This match belongs to another employer")
    return result


def _score_candidate(candidate: Candidate, job: JobPosting) -> MatchCandidateResponse:
    rule_result = RuleBasedMatcher().check_hard_filters(
        CandidateRuleData(
            years_experience=candidate.years_experience,
            location=candidate.location,
            expected_salary=candidate.expected_salary,
            certifications=frozenset(candidate.certifications or []),
            work_authorized=getattr(candidate, "work_authorized", None),
        ),
        JobRuleData(
            required_experience_years=job.required_experience_years,
            location=job.location,
            salary_range_max=job.salary_range_max,
            mandatory_certifications=frozenset(job.mandatory_certifications or []),
            requires_work_authorization=getattr(job, "requires_work_authorization", False),
        ),
    )
    if not rule_result.passed:
        return MatchCandidateResponse(
            candidate_id=candidate.candidate_id,
            full_name=candidate.full_name,
            hard_rule_passed=False,
            rule_reasons=list(rule_result.reasons),
            skill_overlap=0.0,
            semantic_score=0.0,
            growth_score=0.0,
            final_score=0.0,
        )

    candidate_skills = {skill.casefold() for skill in (candidate.skills or [])}
    required_skills = {skill.casefold() for skill in (job.required_skills or [])}
    overlap = len(candidate_skills & required_skills) / len(required_skills) if required_skills else 0.0
    semantic_score = semantic_similarity(candidate.parsed_resume_text or "", job.description)
    experience_score = min(candidate.years_experience / max(job.required_experience_years, 1), 1.0)
    growth_score = (experience_score + min(len(candidate.certifications or []) / 2, 1.0)) / 2
    final_score, _ = calibrated_score(semantic_score, overlap, growth_score)
    return MatchCandidateResponse(
        candidate_id=candidate.candidate_id,
        full_name=candidate.full_name,
        hard_rule_passed=rule_result.passed,
        rule_reasons=list(rule_result.reasons),
        skill_overlap=round(overlap, 4),
        semantic_score=round(semantic_score, 4),
        growth_score=round(growth_score, 4),
        final_score=final_score,
    )


@router.post("/evaluate/{job_id}", response_model=MatchEvaluationResponse)
def evaluate_matches(
    job_id: UUID,
    user: User = Depends(require_roles(UserRole.recruiter, UserRole.admin)),
    db: Session = Depends(get_db),
) -> MatchEvaluationResponse:
    job = db.get(JobPosting, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job posting not found")
    if user.role != UserRole.admin:
        employer = db.get(Employer, job.employer_id)
        if employer is None or employer.user_id != user.user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only evaluate your own job postings")
    candidates = list(db.scalars(select(Candidate).join(User, Candidate.user_id == User.user_id).where(User.is_active.is_(True)).order_by(Candidate.created_at.asc())))
    ranked = sorted((_score_candidate(candidate, job) for candidate in candidates), key=lambda result: result.final_score, reverse=True)
    candidates_by_id = {candidate.candidate_id: candidate for candidate in candidates}
    required_skills = {skill.casefold() for skill in (job.required_skills or [])}
    for result in ranked:
        result.match_id = uuid4()
        candidate = candidates_by_id[result.candidate_id]
        matched_skills = sorted({skill for skill in (candidate.skills or []) if skill.casefold() in required_skills})
        missing_skills = sorted({skill for skill in (job.required_skills or []) if skill.casefold() not in {item.casefold() for item in (candidate.skills or [])}})
        db.add(MatchResult(
            match_id=result.match_id,
            job_id=job.job_id,
            candidate_id=result.candidate_id,
            hard_rule_passed=result.hard_rule_passed,
            similarity_score=result.semantic_score,
            growth_score=result.growth_score,
            skill_overlap_score=result.skill_overlap,
            model_version="legacy-calibration-unverified-serving-v1",
            final_weighted_score=result.final_score,
            skill_gap_breakdown={"matched_skills": matched_skills, "missing_skills": missing_skills, "rule_reasons": result.rule_reasons},
        ))
    db.add(AuditEvent(actor_user_id=user.user_id, action="matches.evaluated", resource_type="job", resource_id=job.job_id, details={"candidates": len(ranked), "eligible": sum(result.hard_rule_passed for result in ranked)}))
    db.commit()
    return MatchEvaluationResponse(job_id=job.job_id, candidates=ranked)