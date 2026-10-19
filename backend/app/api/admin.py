from uuid import UUID
import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from app.core.rate_limit import limiter
from sqlalchemy import String, and_, cast, exists, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.api.dependencies import require_roles
from app.db.models import AuditEvent, Candidate, Employer, GraphSyncEvent, JobApplication, JobPosting, JobStatus, MatchResult, User, UserRole
from app.db.postgres import get_db
from app.schemas import AccountStatusUpdate, AdminJobResponse, AdminOversightSummary, AdminOverviewResponse, AdminRecruiterResponse, AdminUserResponse, AuditEventResponse, JobResponse, JobStatusUpdate, OntologyRelationRequest, OntologySkillRequest, ResetAuthorization
from app.db.neo4j_db import get_neo4j_driver
from neo4j.exceptions import Neo4jError, ServiceUnavailable, SessionExpired
from app.utils.security import verify_password

router = APIRouter(prefix="/admin", tags=["administration"])

# An open posting with no applicants after this many days is flagged for review.
STALE_AFTER_DAYS = 14


def _stale_cutoff() -> datetime:
    return datetime.now(UTC) - timedelta(days=STALE_AFTER_DAYS)


def _is_stale(cutoff: datetime):
    # Aliased so the subquery still has its own FROM when the outer query already joins applications.
    application = aliased(JobApplication)
    return and_(JobPosting.status == JobStatus.open, JobPosting.posted_at < cutoff, ~exists().where(application.job_id == JobPosting.job_id))


def _needs_attention(cutoff: datetime):
    # Expects the recruiter's User row to be joined: a suspended recruiter's open roles stay visible to candidates.
    return and_(JobPosting.status == JobStatus.open, or_(User.is_active.is_(False), _is_stale(cutoff)))


@router.get("/ontology")
def read_ontology(search: str = Query(default="", max_length=120), user: User = Depends(require_roles(UserRole.admin))):
    try:
        with get_neo4j_driver() as driver, driver.session(database="neo4j") as graph:
            skills = graph.run("MATCH (skill:Skill) WHERE toLower(skill.name) CONTAINS $search RETURN skill.name AS name, skill.category AS category, skill.source AS source ORDER BY skill.name LIMIT 200", search=search.strip().lower()).data()
            links = graph.run("MATCH (source:Skill)-[edge:RELATED_TO]->(target:Skill) WHERE toLower(source.name) CONTAINS $search OR toLower(target.name) CONTAINS $search RETURN source.name AS source_skill, target.name AS target_skill, edge.weight AS weight, edge.source AS source ORDER BY source.name, target.name LIMIT 200", search=search.strip().lower()).data()
            return {"skills": skills, "relationships": links}
    except (Neo4jError, ServiceUnavailable, SessionExpired):
        raise HTTPException(status_code=503, detail="Ontology service unavailable") from None


@router.put("/ontology/skills")
def update_ontology_skill(payload: OntologySkillRequest, user: User = Depends(require_roles(UserRole.admin)), db: Session = Depends(get_db)):
    db.add(AuditEvent(actor_user_id=user.user_id, action="ontology.skill_requested", resource_type="ontology", details=payload.model_dump()))
    db.commit()
    try:
        with get_neo4j_driver() as driver, driver.session(database="neo4j") as graph:
            def update(transaction):
                existing = transaction.run("MATCH (skill:Skill) WHERE toLower(trim(skill.name)) = $name RETURN skill.name AS name ORDER BY skill.name LIMIT 1", name=payload.name.lower()).single()
                name = existing["name"] if existing else payload.name.lower()
                transaction.run("MERGE (skill:Skill {name:$name}) SET skill.category=$category, skill.source=$source", name=name, category=payload.category, source=payload.source).consume()
                return {"name": name, "category": payload.category, "source": payload.source}
            result = graph.execute_write(update)
    except (Neo4jError, ServiceUnavailable, SessionExpired):
        raise HTTPException(status_code=503, detail="Ontology update not confirmed; retry after checking connectivity") from None
    db.add(AuditEvent(actor_user_id=user.user_id, action="ontology.skill_updated", resource_type="ontology", details=result))
    db.commit()
    return result


@router.put("/ontology/relationships")
def update_ontology_relationship(payload: OntologyRelationRequest, remove: bool = False, user: User = Depends(require_roles(UserRole.admin)), db: Session = Depends(get_db)):
    db.add(AuditEvent(actor_user_id=user.user_id, action="ontology.relation_requested", resource_type="ontology", details={**payload.model_dump(), "remove": remove}))
    db.commit()
    try:
        with get_neo4j_driver() as driver, driver.session(database="neo4j") as graph:
            def update(transaction):
                source = transaction.run("MATCH (skill:Skill) WHERE toLower(trim(skill.name))=$name RETURN skill.name AS name ORDER BY skill.name LIMIT 1", name=payload.source_skill.strip().lower()).single()
                target = transaction.run("MATCH (skill:Skill) WHERE toLower(trim(skill.name))=$name RETURN skill.name AS name ORDER BY skill.name LIMIT 1", name=payload.target_skill.strip().lower()).single()
                if not source or not target:
                    raise HTTPException(status_code=404, detail="Both skills must exist before linking them")
                query = "MATCH (source:Skill {name:$source_name})-[edge:RELATED_TO]->(target:Skill {name:$target_name}) DELETE edge" if remove else "MATCH (source:Skill {name:$source_name}), (target:Skill {name:$target_name}) MERGE (source)-[edge:RELATED_TO]->(target) SET edge.weight=$weight, edge.source=$provenance"
                transaction.run(query, source_name=source["name"], target_name=target["name"], weight=payload.weight, provenance=payload.source).consume()
            graph.execute_write(update)
    except (Neo4jError, ServiceUnavailable, SessionExpired):
        raise HTTPException(status_code=503, detail="Ontology update not confirmed; retry after checking connectivity") from None
    db.add(AuditEvent(actor_user_id=user.user_id, action="ontology.relation_removed" if remove else "ontology.relation_updated", resource_type="ontology", details=payload.model_dump()))
    db.commit()
    return {"status": "removed" if remove else "updated"}


@router.post("/users/{user_id}/password-reset")
@limiter.limit("5/minute")
def issue_password_reset(request: Request, user_id: UUID, payload: ResetAuthorization, user: User = Depends(require_roles(UserRole.admin)), db: Session = Depends(get_db)):
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Administrator password is incorrect")
    account = db.scalar(select(User).where(User.user_id == user_id).with_for_update())
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    if account.role == UserRole.admin or not account.is_active:
        raise HTTPException(status_code=409, detail="Reset requires an active non-administrator account")
    token = secrets.token_urlsafe(32)
    account.password_reset_hash = hashlib.sha256(token.encode()).hexdigest()
    account.password_reset_expires_at = datetime.now(UTC) + timedelta(minutes=15)
    db.add(AuditEvent(actor_user_id=user.user_id, action="account.reset_issued", resource_type="user", resource_id=user_id))
    db.commit()
    return {"token": token, "expires_at": account.password_reset_expires_at}


def _user_response(user: User, db: Session) -> AdminUserResponse:
    candidate = db.scalar(select(Candidate).where(Candidate.user_id == user.user_id)) if user.role == UserRole.candidate else None
    employer = db.scalar(select(Employer).where(Employer.user_id == user.user_id)) if user.role == UserRole.recruiter else None
    return AdminUserResponse(user_id=user.user_id, email=user.email, role=user.role, display_name=candidate.full_name if candidate else (employer.contact_name or employer.company_name) if employer else "Administrator", company_name=employer.company_name if employer else None, is_active=user.is_active, is_demo=user.is_demo, created_at=user.created_at)


@router.get("/users", response_model=list[AdminUserResponse])
def list_users(search: str = Query(default="", max_length=120), offset: int = Query(default=0, ge=0), user: User = Depends(require_roles(UserRole.admin)), db: Session = Depends(get_db)):
    statement = select(User).outerjoin(Candidate, Candidate.user_id == User.user_id).outerjoin(Employer, Employer.user_id == User.user_id)
    if search.strip():
        term = search.strip()
        statement = statement.where(User.email.icontains(term, autoescape=True) | Candidate.full_name.icontains(term, autoescape=True) | Employer.contact_name.icontains(term, autoescape=True) | Employer.company_name.icontains(term, autoescape=True))
    return [_user_response(account, db) for account in db.scalars(statement.order_by(User.created_at.desc(), User.user_id).offset(offset).limit(25))]


@router.patch("/users/{user_id}", response_model=AdminUserResponse)
def change_account_status(user_id: UUID, payload: AccountStatusUpdate, user: User = Depends(require_roles(UserRole.admin)), db: Session = Depends(get_db)):
    account = db.get(User, user_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    if account.role == UserRole.admin:
        raise HTTPException(status_code=409, detail="Administrator accounts cannot be suspended here")
    if account.is_active != payload.is_active:
        account.is_active = payload.is_active
        db.add(AuditEvent(actor_user_id=user.user_id, action="account.reactivated" if payload.is_active else "account.suspended", resource_type="user", resource_id=account.user_id))
        db.commit()
        db.refresh(account)
    return _user_response(account, db)


@router.patch("/jobs/{job_id}", response_model=JobResponse)
def moderate_job(job_id: UUID, payload: JobStatusUpdate, user: User = Depends(require_roles(UserRole.admin)), db: Session = Depends(get_db)):
    job = db.get(JobPosting, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != payload.status:
        job.status = payload.status
        db.add(AuditEvent(actor_user_id=user.user_id, action=f"job.{payload.status.value}", resource_type="job", resource_id=job_id))
        db.commit()
        db.refresh(job)
    return job


@router.get("/jobs", response_model=list[AdminJobResponse])
def list_all_jobs(
    search: str = Query(default="", max_length=120),
    status_filter: JobStatus | None = Query(default=None, alias="status"),
    employer_id: UUID | None = None,
    attention: bool = False,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=25, ge=1, le=100),
    user: User = Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    statement = (
        select(JobPosting, Employer.company_name, User.email, User.is_active, func.count(JobApplication.application_id))
        .join(Employer, Employer.employer_id == JobPosting.employer_id)
        .join(User, User.user_id == Employer.user_id)
        .outerjoin(JobApplication, JobApplication.job_id == JobPosting.job_id)
    )
    if search.strip():
        term = search.strip()
        statement = statement.where(
            or_(
                JobPosting.title.icontains(term, autoescape=True),
                Employer.company_name.icontains(term, autoescape=True),
                User.email.icontains(term, autoescape=True),
                cast(JobPosting.required_skills, String).icontains(term, autoescape=True),
            )
        )
    if status_filter is not None:
        statement = statement.where(JobPosting.status == status_filter)
    if employer_id is not None:
        statement = statement.where(JobPosting.employer_id == employer_id)
    if attention:
        statement = statement.where(_needs_attention(_stale_cutoff()))
    statement = (
        statement.group_by(JobPosting.job_id, Employer.company_name, User.email, User.is_active)
        .order_by(JobPosting.posted_at.desc(), JobPosting.job_id)
        .offset(offset)
        .limit(limit)
    )
    rows = db.execute(statement).all()
    return [
        AdminJobResponse(
            **JobResponse.model_validate(job).model_dump(),
            employer_id=job.employer_id,
            company_name=company_name,
            recruiter_email=recruiter_email,
            recruiter_active=recruiter_active,
            applicant_count=applicant_count,
        )
        for job, company_name, recruiter_email, recruiter_active, applicant_count in rows
    ]


@router.get("/recruiters/summary", response_model=AdminOversightSummary)
def read_oversight_summary(user: User = Depends(require_roles(UserRole.admin)), db: Session = Depends(get_db)):
    cutoff = _stale_cutoff()
    owned_jobs = select(func.count(JobPosting.job_id)).join(Employer, Employer.employer_id == JobPosting.employer_id).join(User, User.user_id == Employer.user_id)
    return AdminOversightSummary(
        recruiters_count=db.scalar(select(func.count()).select_from(Employer)) or 0,
        active_recruiters_count=db.scalar(select(func.count()).select_from(Employer).join(User, User.user_id == Employer.user_id).where(User.is_active.is_(True))) or 0,
        jobs_open=db.scalar(select(func.count()).select_from(JobPosting).where(JobPosting.status == JobStatus.open)) or 0,
        jobs_closed=db.scalar(select(func.count()).select_from(JobPosting).where(JobPosting.status == JobStatus.closed)) or 0,
        applications_total=db.scalar(select(func.count()).select_from(JobApplication)) or 0,
        hired_total=db.scalar(select(func.count()).select_from(JobApplication).where(JobApplication.status == "hired")) or 0,
        stale_open_jobs=db.scalar(owned_jobs.where(_is_stale(cutoff))) or 0,
        suspended_open_jobs=db.scalar(owned_jobs.where(JobPosting.status == JobStatus.open, User.is_active.is_(False))) or 0,
        attention_jobs=db.scalar(owned_jobs.where(_needs_attention(cutoff))) or 0,
        stale_after_days=STALE_AFTER_DAYS,
    )


@router.get("/recruiters", response_model=list[AdminRecruiterResponse])
def list_recruiters(
    search: str = Query(default="", max_length=120),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=25, ge=1, le=100),
    user: User = Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    cutoff = _stale_cutoff()
    # Applications are aggregated per job first so the per-employer job counts are not multiplied by applicants.
    applications = (
        select(
            JobApplication.job_id,
            func.count(JobApplication.application_id).label("applications"),
            func.count(JobApplication.application_id).filter(JobApplication.status == "hired").label("hired"),
        )
        .group_by(JobApplication.job_id)
        .subquery()
    )
    jobs = (
        select(
            JobPosting.employer_id,
            func.count(JobPosting.job_id).label("jobs_total"),
            func.count(JobPosting.job_id).filter(JobPosting.status == JobStatus.open).label("jobs_open"),
            func.coalesce(func.sum(applications.c.applications), 0).label("applications_total"),
            func.coalesce(func.sum(applications.c.hired), 0).label("hired_total"),
            func.count(JobPosting.job_id).filter(JobPosting.status == JobStatus.open, JobPosting.posted_at < cutoff, applications.c.job_id.is_(None)).label("stale_open_jobs"),
            func.max(JobPosting.posted_at).label("last_posted_at"),
        )
        .outerjoin(applications, applications.c.job_id == JobPosting.job_id)
        .group_by(JobPosting.employer_id)
        .subquery()
    )
    statement = (
        select(
            Employer, User.email, User.is_active, User.is_demo,
            func.coalesce(jobs.c.jobs_total, 0), func.coalesce(jobs.c.jobs_open, 0),
            func.coalesce(jobs.c.applications_total, 0), func.coalesce(jobs.c.hired_total, 0),
            func.coalesce(jobs.c.stale_open_jobs, 0), jobs.c.last_posted_at,
        )
        .join(User, User.user_id == Employer.user_id)
        .outerjoin(jobs, jobs.c.employer_id == Employer.employer_id)
    )
    if search.strip():
        term = search.strip()
        statement = statement.where(
            or_(
                Employer.company_name.icontains(term, autoescape=True),
                Employer.contact_name.icontains(term, autoescape=True),
                User.email.icontains(term, autoescape=True),
            )
        )
    statement = statement.order_by(jobs.c.last_posted_at.desc().nulls_last(), Employer.company_name, Employer.employer_id).offset(offset).limit(limit)
    return [
        AdminRecruiterResponse(
            employer_id=employer.employer_id, user_id=employer.user_id, company_name=employer.company_name,
            contact_name=employer.contact_name, email=email, is_active=is_active, is_demo=is_demo,
            jobs_total=jobs_total, jobs_open=jobs_open, applications_total=applications_total,
            hired_total=hired_total, stale_open_jobs=stale_open_jobs, last_posted_at=last_posted_at,
        )
        for employer, email, is_active, is_demo, jobs_total, jobs_open, applications_total, hired_total, stale_open_jobs, last_posted_at in db.execute(statement).all()
    ]


@router.get("/overview", response_model=AdminOverviewResponse)
def read_admin_overview(
    user: User = Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> AdminOverviewResponse:
    recent_users = list(db.scalars(select(User).order_by(User.created_at.desc()).limit(10)))
    recent_jobs = list(db.scalars(select(JobPosting).order_by(JobPosting.posted_at.desc()).limit(10)))
    return AdminOverviewResponse(
        users_count=db.scalar(select(func.count()).select_from(User)) or 0,
        candidates_count=db.scalar(select(func.count()).select_from(Candidate)) or 0,
        employers_count=db.scalar(select(func.count()).select_from(Employer)) or 0,
        jobs_count=db.scalar(select(func.count()).select_from(JobPosting)) or 0,
        match_results_count=db.scalar(select(func.count()).select_from(MatchResult)) or 0,
        applications_count=db.scalar(select(func.count()).select_from(JobApplication)) or 0,
        pending_graph_events=db.scalar(select(func.count()).select_from(GraphSyncEvent)) or 0,
        suspended_users_count=db.scalar(select(func.count()).select_from(User).where(User.is_active.is_(False))) or 0,
        recent_users=[_user_response(item, db) for item in recent_users],
        recent_jobs=[JobResponse.model_validate(item) for item in recent_jobs],
        recent_activity=[
            AuditEventResponse.model_validate(event).model_copy(update={"actor_email": actor_email})
            for event, actor_email in db.execute(select(AuditEvent, User.email).outerjoin(User, User.user_id == AuditEvent.actor_user_id).order_by(AuditEvent.created_at.desc()).limit(30)).all()
        ],
    )