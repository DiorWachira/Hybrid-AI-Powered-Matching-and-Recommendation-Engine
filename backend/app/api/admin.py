from uuid import UUID
import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from app.core.rate_limit import limiter
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.db.models import AuditEvent, Candidate, Employer, GraphSyncEvent, JobApplication, JobPosting, MatchResult, User, UserRole
from app.db.postgres import get_db
from app.schemas import AccountStatusUpdate, AdminOverviewResponse, AdminUserResponse, AuditEventResponse, JobResponse, JobStatusUpdate, OntologyRelationRequest, OntologySkillRequest, ResetAuthorization
from app.db.neo4j_db import get_neo4j_driver
from neo4j.exceptions import Neo4jError, ServiceUnavailable, SessionExpired
from app.utils.security import verify_password

router = APIRouter(prefix="/admin", tags=["administration"])


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
        recent_activity=[AuditEventResponse.model_validate(item) for item in db.scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(30))],
    )