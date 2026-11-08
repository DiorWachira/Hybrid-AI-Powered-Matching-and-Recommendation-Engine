"""One-screen hiring flow on top of a job's latest evaluation, its simulated run, and the recruiter's filled roles."""
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.api.jobs import APPLICATION_TRANSITIONS, _owned_job, override_checks, require_override_reason
from app.api.matches import latest_scores
from app.core.hiring_plan import ACTIVE_STATUSES, RankedApplicant, plan_simulation
from app.core.hybrid_matcher import _artifact
from app.core.overrides import audit_details
from app.core.rate_limit import limiter
from app.db.models import AuditEvent, Candidate, Employer, HiringSimulation, JobApplication, JobPosting, JobStatus, User, UserRole
from app.db.postgres import get_db
from app.schemas import BulkApplicationUpdate, FilledRole, FilledRoleHire, HiringApplicant, HiringCompleteRequest, HiringFlowResponse, HiringSimulationInfo, HiringSimulationRequest, HiringSimulationResponse, HiringSimulationStep

router = APIRouter(prefix="/jobs", tags=["hiring"])


def _simulation_info(db: Session, simulation: HiringSimulation | None) -> HiringSimulationInfo | None:
    if simulation is None:
        return None
    hired = db.get(JobApplication, simulation.hired_application_id) if simulation.hired_application_id else None
    candidate = db.get(Candidate, hired.candidate_id) if hired else None
    return HiringSimulationInfo(ran_at=simulation.created_at, hired_name=candidate.full_name if candidate else None)


def _flow(db: Session, job: JobPosting) -> HiringFlowResponse:
    evaluated_at, scores = latest_scores(db, job.job_id)
    threshold = _artifact()["decision_threshold"]
    rows = db.execute(
        select(JobApplication, Candidate.full_name, Candidate.location, Candidate.years_experience)
        .join(Candidate, Candidate.candidate_id == JobApplication.candidate_id)
        .where(JobApplication.job_id == job.job_id)
    ).all()
    applicants = []
    for application, name, location, years in rows:
        match = scores.get(application.candidate_id)
        score = match.final_weighted_score if match else None
        applicants.append(HiringApplicant(
            application_id=application.application_id, candidate_id=application.candidate_id, candidate_name=name,
            candidate_location=location, years_experience=years, status=application.status, final_score=score,
            hard_rule_passed=match.hard_rule_passed if match else None,
            recommended=bool(match.hard_rule_passed and (score or 0) >= threshold) if match else None,
            updated_at=application.updated_at,
            rule_reasons=list((match.skill_gap_breakdown or {}).get("rule_reasons") or []) if match else [],
        ))
    applicants.sort(key=lambda item: (item.final_score is None, -(item.final_score or 0), str(item.application_id)))
    return HiringFlowResponse(
        job_id=job.job_id, job_status=job.status.value, evaluated_at=evaluated_at, applicants=applicants,
        simulation=_simulation_info(db, db.get(HiringSimulation, job.job_id)),
    )


@router.get("/mine/filled", response_model=list[FilledRole])
def filled_roles(user: User = Depends(require_roles(UserRole.recruiter)), db: Session = Depends(get_db)):
    rows = db.execute(
        select(JobPosting, JobApplication, Candidate.full_name)
        .join(Employer, JobPosting.employer_id == Employer.employer_id)
        .join(JobApplication, JobApplication.job_id == JobPosting.job_id)
        .join(Candidate, Candidate.candidate_id == JobApplication.candidate_id)
        .where(Employer.user_id == user.user_id, JobApplication.status == "hired")
        .order_by(JobApplication.updated_at.desc(), JobApplication.application_id)
    ).all()
    roles: dict[UUID, FilledRole] = {}
    for job, application, name in rows:
        if job.job_id not in roles:
            applicants = db.scalar(select(func.count()).select_from(JobApplication).where(JobApplication.job_id == job.job_id)) or 0
            roles[job.job_id] = FilledRole(job_id=job.job_id, title=job.title, location=job.location, job_status=job.status.value, posted_at=job.posted_at, applicants_total=applicants, hires=[])
        simulation = db.get(HiringSimulation, job.job_id)
        _, scores = latest_scores(db, job.job_id)
        match = scores.get(application.candidate_id)
        simulated = bool(simulation and simulation.hired_application_id == application.application_id)
        roles[job.job_id].hires.append(FilledRoleHire(
            application_id=application.application_id, candidate_name=name, final_score=match.final_weighted_score if match else None,
            hired_at=application.updated_at, days_to_fill=max(0, (application.updated_at - job.posted_at).days) if job.posted_at else None, simulated=simulated,
        ))
    return list(roles.values())


@router.get("/{job_id}/hiring", response_model=HiringFlowResponse)
def read_hiring_flow(job_id: UUID, user: User = Depends(require_roles(UserRole.recruiter)), db: Session = Depends(get_db)):
    return _flow(db, _owned_job(db, user, job_id))


@router.post("/{job_id}/hiring/advance", response_model=HiringFlowResponse)
def advance_applications(job_id: UUID, payload: BulkApplicationUpdate, user: User = Depends(require_roles(UserRole.recruiter)), db: Session = Depends(get_db)):
    """Move several applicants at once. All of them move, or none do."""
    job = _owned_job(db, user, job_id)
    wanted = set(payload.application_ids)
    applications = list(db.scalars(select(JobApplication).where(JobApplication.job_id == job_id, JobApplication.application_id.in_(wanted)).with_for_update()))
    if len(applications) != len(wanted):
        raise HTTPException(status_code=404, detail="Application not found")
    if any(payload.status not in APPLICATION_TRANSITIONS.get(application.status, set()) for application in applications):
        raise HTTPException(status_code=409, detail="Application status transition not allowed")
    checks = override_checks(db, job_id, applications, payload.status)
    require_override_reason(db, checks, payload.override_reason, applications)
    now = datetime.now(UTC)
    for application in applications:
        application.status = payload.status
        application.updated_at = now
        db.add(AuditEvent(actor_user_id=user.user_id, action="application.status_changed", resource_type="application", resource_id=application.application_id, details=audit_details(payload.status, checks.get(application.application_id), payload.override_reason)))
    db.commit()
    return _flow(db, job)


@router.post("/{job_id}/hiring/complete", response_model=HiringFlowResponse)
def complete_hiring(job_id: UUID, payload: HiringCompleteRequest, user: User = Depends(require_roles(UserRole.recruiter)), db: Session = Depends(get_db)):
    """After a hire: release everyone still waiting and, if asked, close the posting."""
    job = _owned_job(db, user, job_id)
    if not db.scalar(select(JobApplication.application_id).where(JobApplication.job_id == job_id, JobApplication.status == "hired").limit(1)):
        raise HTTPException(status_code=409, detail="Hire someone before completing this role")
    waiting = list(db.scalars(select(JobApplication).where(JobApplication.job_id == job_id, JobApplication.status.in_(ACTIVE_STATUSES)).with_for_update()))
    now = datetime.now(UTC)
    for application in waiting:
        application.status = "rejected"
        application.updated_at = now
        db.add(AuditEvent(actor_user_id=user.user_id, action="application.status_changed", resource_type="application", resource_id=application.application_id, details={"status": "rejected"}))
    if payload.close_posting and job.status != JobStatus.closed:
        job.status = JobStatus.closed
        db.add(AuditEvent(actor_user_id=user.user_id, action="job.closed", resource_type="job", resource_id=job_id))
    db.commit()
    return _flow(db, job)


@router.post("/{job_id}/hiring/simulate", response_model=HiringSimulationResponse)
@limiter.limit("10/minute")
def simulate_hiring(request: Request, job_id: UUID, payload: HiringSimulationRequest, user: User = Depends(require_roles(UserRole.recruiter)), db: Session = Depends(get_db)):
    """Run the remaining stages automatically on demo applicants. Real people are never moved or told they were hired."""
    job = _owned_job(db, user, job_id)
    if job.status != JobStatus.open:
        raise HTTPException(status_code=409, detail="Reopen this posting before simulating")
    if db.get(HiringSimulation, job_id) is not None:
        raise HTTPException(status_code=409, detail="This role already has a simulated hire. Undo it to run again")
    if db.scalar(select(JobApplication.application_id).where(JobApplication.job_id == job_id, JobApplication.status == "hired").limit(1)):
        raise HTTPException(status_code=409, detail="This role already has a hire")
    evaluated_at, scores = latest_scores(db, job_id)
    if evaluated_at is None:
        raise HTTPException(status_code=409, detail="Evaluate candidates before simulating")
    rows = db.execute(
        select(JobApplication, Candidate.full_name, User.is_demo)
        .join(Candidate, Candidate.candidate_id == JobApplication.candidate_id).join(User, User.user_id == Candidate.user_id)
        .where(JobApplication.job_id == job_id).with_for_update(of=JobApplication)
    ).all()
    by_id = {application.application_id: application for application, _, _ in rows}
    real_waiting = sum(1 for application, _, is_demo in rows if not is_demo and application.status in ACTIVE_STATUSES)
    demo = []
    for application, name, is_demo in rows:
        if is_demo:
            match = scores.get(application.candidate_id)
            demo.append(RankedApplicant(application.application_id, name, application.status, match.final_weighted_score if match else None, match.hard_rule_passed if match else None))
    plan = plan_simulation(demo, payload.top_n, payload.interview_count)
    if plan is None:
        raise HTTPException(status_code=409, detail="No eligible demo applicants to simulate with")

    changes = {plan.hired.application_id: "hired", **{item.application_id: "rejected" for item in plan.rejected}}
    now = datetime.now(UTC)
    previous = {}
    for application_id, new_status in changes.items():
        application = by_id[application_id]
        previous[str(application_id)] = {"from": application.status, "to": new_status}
        application.status = new_status
        application.updated_at = now
        db.add(AuditEvent(actor_user_id=user.user_id, action="application.status_changed", resource_type="application", resource_id=application_id, details={"status": new_status, "simulated": True}))
    closes = real_waiting == 0
    db.add(HiringSimulation(job_id=job_id, actor_user_id=user.user_id, hired_application_id=plan.hired.application_id, previous_job_status=job.status.value, previous_statuses=previous, created_at=now))
    if closes:
        job.status = JobStatus.closed
    db.add(AuditEvent(actor_user_id=user.user_id, action="job.hiring_simulated", resource_type="job", resource_id=job_id, created_at=now, details={"hired_application_id": str(plan.hired.application_id), "top_n": payload.top_n, "real_applicants_left": real_waiting}))
    db.commit()

    def names(items):
        return [item.name for item in items]

    steps = [
        HiringSimulationStep(stage="selected", title=f"Top {len(plan.selected)} move on", detail="Ranked by match score among eligible applicants.", candidates=names(plan.selected)),
        HiringSimulationStep(stage="shortlisted", title=f"{len(plan.interviewed)} shortlisted for interview", detail="The strongest of the selected applicants.", candidates=names(plan.interviewed)),
        HiringSimulationStep(stage="interviewed", title="Interviews simulated", detail="No interview took place, so the match score stands in for the result.", candidates=names(plan.interviewed)),
        HiringSimulationStep(stage="hired", title=f"{plan.hired.name} hired", detail=f"Highest match score at {round((plan.hired.score or 0) * 100)}%.", candidates=[plan.hired.name]),
        HiringSimulationStep(stage="closed", title="Posting closed" if closes else "Posting left open", detail=f"{len(plan.rejected)} other demo applicants released." + (f" {real_waiting} real applicants were left untouched." if real_waiting else ""), candidates=[]),
    ]
    return HiringSimulationResponse(steps=steps, real_applicants_left=real_waiting, flow=_flow(db, job))


@router.post("/{job_id}/hiring/simulate/undo", response_model=HiringFlowResponse)
def undo_simulation(job_id: UUID, user: User = Depends(require_roles(UserRole.recruiter)), db: Session = Depends(get_db)):
    """Put a simulated run back. Anything changed by hand since then is left as it is."""
    job = _owned_job(db, user, job_id)
    simulation = db.get(HiringSimulation, job_id)
    if simulation is None:
        raise HTTPException(status_code=404, detail="This role has no simulated hire")
    applications = {str(item.application_id): item for item in db.scalars(select(JobApplication).where(JobApplication.job_id == job_id).with_for_update())}
    now = datetime.now(UTC)
    for application_id, change in simulation.previous_statuses.items():
        application = applications.get(application_id)
        if application is not None and application.status == change["to"]:
            application.status = change["from"]
            application.updated_at = now
    if simulation.previous_job_status == JobStatus.open.value and job.status == JobStatus.closed:
        job.status = JobStatus.open
    db.delete(simulation)
    db.add(AuditEvent(actor_user_id=user.user_id, action="job.hiring_simulation_undone", resource_type="job", resource_id=job_id))
    db.commit()
    return _flow(db, job)
