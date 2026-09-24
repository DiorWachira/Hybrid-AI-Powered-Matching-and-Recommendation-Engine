from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.core.rule_filter import CandidateRuleData, JobRuleData, RuleBasedMatcher
from app.db.models import Candidate, JobPosting, MatchResult, User, UserRole
from app.core.hybrid_matcher import calibrated_score, semantic_similarity
from app.db.postgres import get_db
from app.schemas import MatchCandidateResponse, MatchEvaluationResponse

router = APIRouter(prefix="/matches", tags=["matches"])


def _score_candidate(candidate: Candidate, job: JobPosting) -> MatchCandidateResponse:
    candidate_skills = {skill.casefold() for skill in (candidate.skills or [])}
    required_skills = {skill.casefold() for skill in (job.required_skills or [])}
    overlap = len(candidate_skills & required_skills) / len(required_skills) if required_skills else 0.0
    semantic_score = semantic_similarity(candidate.parsed_resume_text or "", job.description)
    experience_score = min(candidate.years_experience / max(job.required_experience_years, 1), 1.0)
    growth_score = (experience_score + min(len(candidate.certifications or []) / 2, 1.0)) / 2
    rule_result = RuleBasedMatcher().check_hard_filters(
        CandidateRuleData(
            years_experience=candidate.years_experience,
            location=candidate.location,
            expected_salary=candidate.expected_salary,
            certifications=frozenset(candidate.certifications or []),
        ),
        JobRuleData(
            required_experience_years=job.required_experience_years,
            location=job.location,
            salary_range_max=job.salary_range_max,
            mandatory_certifications=frozenset(job.mandatory_certifications or []),
        ),
    )
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
    job_id: str,
    user: User = Depends(require_roles(UserRole.recruiter, UserRole.admin)),
    db: Session = Depends(get_db),
) -> MatchEvaluationResponse:
    job = db.get(JobPosting, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job posting not found")
    candidates = list(db.scalars(select(Candidate).order_by(Candidate.created_at.asc())))
    ranked = sorted((_score_candidate(candidate, job) for candidate in candidates), key=lambda result: result.final_score, reverse=True)
    db.query(MatchResult).filter(MatchResult.job_id == job.job_id).delete(synchronize_session=False)
    candidates_by_id = {candidate.candidate_id: candidate for candidate in candidates}
    required_skills = {skill.casefold() for skill in (job.required_skills or [])}
    for result in ranked:
        candidate = candidates_by_id[result.candidate_id]
        matched_skills = sorted({skill for skill in (candidate.skills or []) if skill.casefold() in required_skills})
        missing_skills = sorted({skill for skill in (job.required_skills or []) if skill.casefold() not in {item.casefold() for item in (candidate.skills or [])}})
        db.add(MatchResult(
            job_id=job.job_id,
            candidate_id=result.candidate_id,
            hard_rule_passed=result.hard_rule_passed,
            similarity_score=result.semantic_score,
            growth_score=result.growth_score,
            final_weighted_score=result.final_score,
            skill_gap_breakdown={"matched_skills": matched_skills, "missing_skills": missing_skills, "rule_reasons": result.rule_reasons},
        ))
    db.commit()
    return MatchEvaluationResponse(job_id=job.job_id, candidates=ranked)