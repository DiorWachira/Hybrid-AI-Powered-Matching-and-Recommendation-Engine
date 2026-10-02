from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.db.models import AuditEvent, Candidate, Employer, GraphSyncEvent, JobApplication, JobPosting, MatchResult, User, UserRole
from app.db.postgres import get_db
from app.schemas import AccountStatusUpdate, AdminOverviewResponse, AdminUserResponse, AuditEventResponse, JobResponse, JobStatusUpdate

router = APIRouter(prefix="/admin", tags=["administration"])


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