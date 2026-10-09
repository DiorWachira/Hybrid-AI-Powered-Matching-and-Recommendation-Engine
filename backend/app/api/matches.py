from uuid import UUID, uuid4
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from app.core.rate_limit import limiter
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.core.rule_filter import CandidateRuleData, JobRuleData, RuleBasedMatcher
from app.db.models import AuditEvent, Candidate, Employer, JobPosting, MatchResult, User, UserRole
from app.core.hybrid_matcher import calibrated_score, semantic_similarity
from app.core.match_features import growth_score as feature_growth_score, skill_overlap
from app.db.postgres import get_db
from app.schemas import MatchCandidateResponse, MatchEvaluationResponse, StoredMatchResponse
from app.db.neo4j_db import get_neo4j_driver
from neo4j.exceptions import Neo4jError, ServiceUnavailable, SessionExpired

router = APIRouter(prefix="/matches", tags=["matches"])


@router.get("/jobs/{job_id}", response_model=MatchEvaluationResponse)
def read_job_matches(job_id: UUID, user: User = Depends(require_roles(UserRole.recruiter, UserRole.admin)), db: Session = Depends(get_db)):
    job = db.get(JobPosting, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job posting not found")
    if user.role != UserRole.admin:
        employer = db.get(Employer, job.employer_id)
        if employer is None or employer.user_id != user.user_id:
            raise HTTPException(status_code=403, detail="You can only view your own job evaluations")
    completed = db.scalar(select(AuditEvent).where(AuditEvent.action == "matches.evaluated", AuditEvent.resource_type == "job", AuditEvent.resource_id == job_id).order_by(AuditEvent.created_at.desc(), AuditEvent.event_id.desc()).limit(1))
    evaluated_at = completed.created_at if completed else db.scalar(select(func.max(MatchResult.created_at)).where(MatchResult.job_id == job_id))
    if evaluated_at is None:
        return MatchEvaluationResponse(job_id=job_id, candidates=[])
    rows = db.execute(select(MatchResult, Candidate.full_name).join(Candidate, Candidate.candidate_id == MatchResult.candidate_id).join(User, User.user_id == Candidate.user_id).where(MatchResult.job_id == job_id, MatchResult.created_at == evaluated_at, User.is_active.is_(True)).order_by(MatchResult.final_weighted_score.desc(), MatchResult.candidate_id)).all()
    candidates = []
    for result, name in rows:
        explanation = result.skill_gap_breakdown or {}
        candidates.append(MatchCandidateResponse(
            match_id=result.match_id, candidate_id=result.candidate_id, full_name=name,
            hard_rule_passed=result.hard_rule_passed, rule_reasons=explanation.get("rule_reasons", []),
            skill_overlap=result.skill_overlap_score or 0.0, semantic_score=result.similarity_score or 0.0,
            growth_score=result.growth_score or 0.0, final_score=result.final_weighted_score or 0.0,
            matched_skills=explanation.get("matched_skills"), missing_skills=explanation.get("missing_skills"), model_version=result.model_version,
        ))
    return MatchEvaluationResponse(job_id=job_id, evaluated_at=evaluated_at, candidates=candidates)


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


@router.get("/{match_id}/graph")
def read_match_graph(match_id: UUID, user: User = Depends(require_roles(UserRole.candidate, UserRole.recruiter, UserRole.admin)), db: Session = Depends(get_db)):
    result = read_match(match_id, user, db)
    candidate_id, job_id = str(result.candidate_id), str(result.job_id)
    try:
        with get_neo4j_driver() as driver, driver.session(database="neo4j") as graph:
            entities = graph.run("MATCH (candidate:Candidate {id:$candidate}), (job:Job {id:$job}) RETURN job.title AS title", candidate=candidate_id, job=job_id).single()
            if entities is None:
                return {"nodes": [], "edges": [], "state": "awaiting_projection", "truncated": False}
            candidate_skills = [row["name"] for row in graph.run("MATCH (:Candidate {id:$candidate})-[:HAS_SKILL]->(skill:Skill) RETURN DISTINCT skill.name AS name ORDER BY name LIMIT 26", candidate=candidate_id)]
            required_skills = [row["name"] for row in graph.run("MATCH (:Job {id:$job})-[:REQUIRES_SKILL]->(skill:Skill) RETURN DISTINCT skill.name AS name ORDER BY name LIMIT 26", job=job_id)]
            truncated = len(candidate_skills) > 25 or len(required_skills) > 25
            candidate_skills, required_skills = candidate_skills[:25], required_skills[:25]
            skill_names = sorted(set(candidate_skills + required_skills))
            nodes = [{"id": "candidate", "label": "Candidate", "kind": "candidate"}, {"id": "job", "label": entities["title"] or "Job", "kind": "job"}]
            nodes.extend({"id": "skill:" + name, "label": name, "kind": "skill"} for name in skill_names)
            edges = [{"id": "has:" + name, "source": "candidate", "target": "skill:" + name, "label": "HAS_SKILL"} for name in candidate_skills]
            edges.extend({"id": "requires:" + name, "source": "job", "target": "skill:" + name, "label": "REQUIRES_SKILL"} for name in required_skills)
            links = graph.run("MATCH (source:Skill)-[edge:RELATED_TO]->(target:Skill) WHERE source.name IN $names AND target.name IN $names RETURN source.name AS source, target.name AS target, edge.weight AS weight ORDER BY source.name, target.name LIMIT 51", names=skill_names).data()
            truncated = truncated or len(links) > 50
            for index, link in enumerate(links[:50]):
                edges.append({"id": f"related:{index}", "source": "skill:" + link["source"], "target": "skill:" + link["target"], "label": "RELATED_TO", "weight": link["weight"]})
            applications = graph.run("MATCH (:Candidate {id:$candidate})-[edge:APPLIED_TO]->(:Job {id:$job}) RETURN edge.status AS status LIMIT 1", candidate=candidate_id, job=job_id).single()
            if applications:
                edges.append({"id": "application", "source": "candidate", "target": "job", "label": "APPLIED_TO", "status": applications["status"]})
            return {"nodes": nodes, "edges": edges, "state": "current_projection", "truncated": truncated}
    except (Neo4jError, ServiceUnavailable, SessionExpired):
        raise HTTPException(status_code=503, detail="Skill graph is unavailable; saved evaluation is still accessible") from None


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

    overlap = skill_overlap(candidate.skills or [], job.required_skills or [])
    semantic_score = semantic_similarity(candidate.parsed_resume_text or "", job.description)
    growth_score = feature_growth_score(candidate.years_experience, job.required_experience_years, len(candidate.certifications or []))
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
@limiter.limit("10/minute")
def evaluate_matches(
    request: Request,
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
    ranked = sorted((_score_candidate(candidate, job) for candidate in candidates), key=lambda result: (-result.final_score, str(result.candidate_id)))
    evaluated_at = datetime.now(UTC)
    candidates_by_id = {candidate.candidate_id: candidate for candidate in candidates}
    required_skills = {skill.casefold() for skill in (job.required_skills or [])}
    for result in ranked:
        result.match_id = uuid4()
        candidate = candidates_by_id[result.candidate_id]
        matched_skills = sorted({skill for skill in (candidate.skills or []) if skill.casefold() in required_skills})
        missing_skills = sorted({skill for skill in (job.required_skills or []) if skill.casefold() not in {item.casefold() for item in (candidate.skills or [])}})
        result.matched_skills = matched_skills
        result.missing_skills = missing_skills
        result.model_version = "legacy-calibration-unverified-serving-v1"
        db.add(MatchResult(
            match_id=result.match_id,
            created_at=evaluated_at,
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
    db.add(AuditEvent(actor_user_id=user.user_id, action="matches.evaluated", resource_type="job", resource_id=job.job_id, created_at=evaluated_at, details={"candidates": len(ranked), "eligible": sum(result.hard_rule_passed for result in ranked)}))
    db.commit()
    return MatchEvaluationResponse(job_id=job.job_id, evaluated_at=evaluated_at, candidates=ranked)