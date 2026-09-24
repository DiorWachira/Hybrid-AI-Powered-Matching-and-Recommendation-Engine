from io import BytesIO
from pathlib import Path
import re

from docx import Document
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.db.models import Candidate, CandidateOpportunity, Employer, JobPosting, JobStatus, OpportunityStatus, User, UserRole
from app.db.neo4j_db import project_candidate_skills
from app.db.postgres import get_db
from app.schemas import CandidateDashboardResponse, CandidateProfileResponse, CandidateProfileUpdate, OpportunityActionRequest, OpportunityResponse
from app.api.matches import _score_candidate

router = APIRouter(prefix="/candidates", tags=["candidates"])
MAX_RESUME_BYTES = 10 * 1024 * 1024
KNOWN_SKILLS = ("python", "sql", "data analysis", "excel", "power bi", "docker", "kubernetes", "ci/cd", "linux", "aws", "terraform", "ansible", "git", "rest apis", "system design", "financial accounting", "taxation", "business analysis", "project management")


def _extract_text(filename: str, content: bytes) -> str:
    suffix = Path(filename).suffix.casefold()
    if suffix == ".pdf":
        return "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(content)).pages).strip()
    if suffix == ".docx":
        document = Document(BytesIO(content))
        return "\n".join(paragraph.text for paragraph in document.paragraphs).strip()
    raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Only PDF and DOCX resumes are supported")


def _skills_from_text(text: str) -> list[str]:
    normalised = text.casefold()
    return [skill for skill in KNOWN_SKILLS if re.search(rf"(?<![a-z0-9]){re.escape(skill)}(?![a-z0-9])", normalised)]


def _opportunity(job: JobPosting, score: float, status_value: OpportunityStatus | None, company_name: str) -> OpportunityResponse:
    return OpportunityResponse(
        job_id=job.job_id,
        title=job.title,
        company_name=company_name,
        description=job.description,
        location=job.location,
        salary_range_max=job.salary_range_max,
        required_experience_years=job.required_experience_years,
        required_skills=job.required_skills or [],
        mandatory_certifications=job.mandatory_certifications or [],
        match_score=round(score, 4),
        status=status_value,
    )


@router.get("/me", response_model=CandidateProfileResponse)
def read_candidate_profile(
    user: User = Depends(require_roles(UserRole.candidate)),
    db: Session = Depends(get_db),
) -> Candidate:
    candidate = db.query(Candidate).filter(Candidate.user_id == user.user_id).first()
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate profile not found")
    return candidate


@router.put("/me", response_model=CandidateProfileResponse)
def update_candidate_profile(
    payload: CandidateProfileUpdate,
    user: User = Depends(require_roles(UserRole.candidate)),
    db: Session = Depends(get_db),
) -> Candidate:
    candidate = db.query(Candidate).filter(Candidate.user_id == user.user_id).first()
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate profile not found")
    for field, value in payload.model_dump().items():
        setattr(candidate, field, value)
    db.commit()
    db.refresh(candidate)
    return candidate


@router.post("/upload-resume", response_model=CandidateProfileResponse)
async def upload_resume(
    resume: UploadFile = File(...),
    user: User = Depends(require_roles(UserRole.candidate)),
    db: Session = Depends(get_db),
) -> Candidate:
    candidate = db.query(Candidate).filter(Candidate.user_id == user.user_id).first()
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate profile not found")
    filename = resume.filename or "resume"
    if Path(filename).suffix.casefold() not in {".pdf", ".docx"}:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Only PDF and DOCX resumes are supported")
    content = await resume.read(MAX_RESUME_BYTES + 1)
    if len(content) > MAX_RESUME_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Resume must be 10 MB or smaller")
    try:
        text = _extract_text(filename, content)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="The resume could not be read") from exc
    if not text:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="The resume contains no readable text")
    candidate.parsed_resume_text = text[:20_000]
    candidate.skills = _skills_from_text(text)
    project_candidate_skills(str(candidate.candidate_id), candidate.skills, candidate.certifications or [])
    db.commit()
    db.refresh(candidate)
    return candidate


@router.get("/dashboard", response_model=CandidateDashboardResponse)
def candidate_dashboard(
    user: User = Depends(require_roles(UserRole.candidate)),
    db: Session = Depends(get_db),
) -> CandidateDashboardResponse:
    candidate = db.scalar(select(Candidate).where(Candidate.user_id == user.user_id))
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate profile not found")
    jobs = list(db.scalars(select(JobPosting).where(JobPosting.status == JobStatus.open).order_by(JobPosting.posted_at.desc()).limit(50)))
    employer_names = {employer.employer_id: employer.company_name for employer in db.scalars(select(Employer))}
    activity = {item.job_id: item for item in db.scalars(select(CandidateOpportunity).where(CandidateOpportunity.candidate_id == candidate.candidate_id))}
    scored = []
    for job in jobs:
        result = _score_candidate(candidate, job)
        scored.append(_opportunity(job, result.final_score, activity.get(job.job_id).status if job.job_id in activity else None, employer_names.get(job.employer_id, "Workforce employer")))
    history = []
    for item in sorted(activity.values(), key=lambda value: value.updated_at, reverse=True):
        if item.job.status == JobStatus.closed or item.status in {OpportunityStatus.saved, OpportunityStatus.applied}:
            history.append(_opportunity(item.job, next((entry.match_score for entry in scored if entry.job_id == item.job_id), 0.0), item.status, employer_names.get(item.job.employer_id, "Workforce employer")))
    return CandidateDashboardResponse(
        available_opportunities=scored[:20],
        for_you=sorted(scored, key=lambda value: value.match_score, reverse=True)[:5],
        history=history[:20],
    )


@router.post("/opportunities/{job_id}", response_model=OpportunityResponse)
def update_opportunity_status(
    job_id: str,
    payload: OpportunityActionRequest,
    user: User = Depends(require_roles(UserRole.candidate)),
    db: Session = Depends(get_db),
) -> OpportunityResponse:
    candidate = db.scalar(select(Candidate).where(Candidate.user_id == user.user_id))
    job = db.get(JobPosting, job_id)
    if candidate is None or job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate or job not found")
    activity = db.scalar(select(CandidateOpportunity).where(CandidateOpportunity.candidate_id == candidate.candidate_id, CandidateOpportunity.job_id == job.job_id))
    if activity is None:
        activity = CandidateOpportunity(candidate_id=candidate.candidate_id, job_id=job.job_id, status=payload.status)
        db.add(activity)
    else:
        activity.status = payload.status
    db.commit()
    result = _score_candidate(candidate, job)
    employer = db.get(Employer, job.employer_id)
    return _opportunity(job, result.final_score, payload.status, employer.company_name if employer else "Workforce employer")