from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.db.models import Employer, JobPosting, User, UserRole
from app.db.neo4j_db import project_job_requirements
from app.db.postgres import get_db
from app.schemas import JobCreateRequest, JobResponse

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
        required_skills=payload.required_skills or None,
        mandatory_certifications=payload.mandatory_certifications or None,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    project_job_requirements(job.title, job.required_skills or [], job.mandatory_certifications or [])
    return job


@router.get("/", response_model=list[JobResponse])
def list_open_jobs(db: Session = Depends(get_db)) -> list[JobPosting]:
    return list(db.scalars(select(JobPosting).order_by(JobPosting.posted_at.desc())))
