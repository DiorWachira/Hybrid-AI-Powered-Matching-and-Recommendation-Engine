from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.db.models import AuditEvent, Employer, JobApplication, JobPosting, JobStatus, User, UserRole
from app.db.postgres import get_db
from app.schemas import ApplicationResponse, ApplicationStatusUpdate, JobCreateRequest, JobResponse, JobUpdateRequest

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("/create", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
def create_job(
    payload: JobCreateRequest,
    user: User = Depends(require_roles(UserRole.recruiter, UserRole.admin)),
    db: Session = Depends(get_db),
) -> JobPosting:
    employer = db.scalar(select(Employer).where(Employer.user_id == user.user_id))
    if employer is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Recruiter account has no employer profile")
    job = JobPosting(
        employer_id=employer.employer_id,
        title=payload.title,
        description=payload.description,
        location=payload.location,
        required_experience_years=payload.required_experience_years,
        salary_range_max=payload.salary_range_max,
        salary_range_min=payload.salary_range_min,
        requires_work_authorization=payload.requires_work_authorization,
        required_skills=payload.required_skills or None,
        mandatory_certifications=payload.mandatory_certifications or None,
    )
    db.add(job)
    db.flush()
    db.add(AuditEvent(actor_user_id=user.user_id, action="job.created", resource_type="job", resource_id=job.job_id))
    db.commit()
    db.refresh(job)
    return job


@router.get("/", response_model=list[JobResponse])
def list_open_jobs(db: Session = Depends(get_db)) -> list[JobPosting]:
    return list(db.scalars(select(JobPosting).where(JobPosting.status == JobStatus.open).order_by(JobPosting.posted_at.desc())))


def _owned_job(db: Session, user: User, job_id: UUID) -> JobPosting:
    job = db.get(JobPosting, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job posting not found")
    employer = db.get(Employer, job.employer_id)
    if user.role != UserRole.admin and (employer is None or employer.user_id != user.user_id):
        raise HTTPException(status_code=403, detail="You can only manage your own job postings")
    return job


@router.put("/{job_id}", response_model=JobResponse)
def update_job(job_id: UUID, payload: JobUpdateRequest, user: User = Depends(require_roles(UserRole.recruiter, UserRole.admin)), db: Session = Depends(get_db)) -> JobPosting:
    job = _owned_job(db, user, job_id)
    for field, value in payload.model_dump().items():
        setattr(job, field, value)
    db.add(AuditEvent(actor_user_id=user.user_id, action="job.updated", resource_type="job", resource_id=job_id, details={"status": job.status.value}))
    db.commit()
    db.refresh(job)
    return job


@router.get("/{job_id}/applications", response_model=list[ApplicationResponse])
def list_applications(job_id: UUID, user: User = Depends(require_roles(UserRole.recruiter, UserRole.admin)), db: Session = Depends(get_db)):
    _owned_job(db, user, job_id)
    return list(db.scalars(select(JobApplication).where(JobApplication.job_id == job_id).order_by(JobApplication.created_at.desc()).limit(100)))


@router.patch("/{job_id}/applications/{application_id}", response_model=ApplicationResponse)
def update_application(job_id: UUID, application_id: UUID, payload: ApplicationStatusUpdate, user: User = Depends(require_roles(UserRole.recruiter, UserRole.admin)), db: Session = Depends(get_db)):
    _owned_job(db, user, job_id)
    application = db.scalar(select(JobApplication).where(JobApplication.application_id == application_id, JobApplication.job_id == job_id).with_for_update())
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    transitions = {
        "submitted": {"reviewing", "shortlisted", "rejected"},
        "reviewing": {"shortlisted", "rejected"},
        "shortlisted": {"hired", "rejected"},
    }
    if payload.status != application.status and payload.status not in transitions.get(application.status, set()):
        raise HTTPException(status_code=409, detail="Application status transition not allowed")
    application.status = payload.status
    db.add(AuditEvent(actor_user_id=user.user_id, action="application.status_changed", resource_type="application", resource_id=application_id, details={"status": payload.status}))
    db.commit()
    db.refresh(application)
    return application
