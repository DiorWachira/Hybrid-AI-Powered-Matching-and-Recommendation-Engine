from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.db.models import AuditEvent, Candidate, Employer, JobApplication, JobPosting, JobStatus, User, UserRole
from app.db.postgres import get_db
from app.schemas import ApplicantResponse, ApplicationResponse, ApplicationStatusUpdate, JobCreateRequest, JobResponse, JobStatusUpdate, JobUpdateRequest

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/mine", response_model=list[JobResponse])
def list_my_jobs(offset: int = Query(default=0, ge=0), limit: int = Query(default=25, ge=1, le=100), user: User = Depends(require_roles(UserRole.recruiter, UserRole.admin)), db: Session = Depends(get_db)):
    return list(db.scalars(select(JobPosting).join(Employer, JobPosting.employer_id == Employer.employer_id).where(Employer.user_id == user.user_id).order_by(JobPosting.posted_at.desc(), JobPosting.job_id).offset(offset).limit(limit)))


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


@router.patch("/{job_id}/status", response_model=JobResponse)
def change_job_status(job_id: UUID, payload: JobStatusUpdate, user: User = Depends(require_roles(UserRole.recruiter, UserRole.admin)), db: Session = Depends(get_db)):
    job = _owned_job(db, user, job_id)
    if job.status != payload.status:
        job.status = payload.status
        db.add(AuditEvent(actor_user_id=user.user_id, action=f"job.{payload.status.value}", resource_type="job", resource_id=job_id))
        db.commit()
        db.refresh(job)
    return job


@router.get("/{job_id}/applications", response_model=list[ApplicantResponse])
def list_applications(job_id: UUID, offset: int = Query(default=0, ge=0), limit: int = Query(default=100, ge=1, le=100), user: User = Depends(require_roles(UserRole.recruiter, UserRole.admin)), db: Session = Depends(get_db)):
    _owned_job(db, user, job_id)
    rows = db.execute(select(JobApplication, Candidate).join(Candidate, Candidate.candidate_id == JobApplication.candidate_id).where(JobApplication.job_id == job_id).order_by(JobApplication.created_at.desc(), JobApplication.application_id).offset(offset).limit(limit)).all()
    return [ApplicantResponse(**ApplicationResponse.model_validate(application).model_dump(), candidate_name=candidate.full_name, candidate_location=candidate.location, years_experience=candidate.years_experience, skills=candidate.skills or [], certifications=candidate.certifications or []) for application, candidate in rows]


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
