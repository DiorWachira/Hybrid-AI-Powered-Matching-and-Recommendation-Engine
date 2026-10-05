from io import BytesIO
from pathlib import Path
from uuid import UUID
from zipfile import ZipFile
import re

from docx import Document
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from app.core.rate_limit import limiter
from pypdf import PdfReader
from starlette.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.db.models import AuditEvent, Candidate, CandidateOpportunity, Employer, JobApplication, JobPosting, JobStatus, OpportunityStatus, User, UserRole
from app.db.postgres import get_db
from app.schemas import ApplicationResponse, CandidateApplicationResponse, CandidateDashboardResponse, CandidateProfileResponse, CandidateProfileUpdate, OpportunityActionRequest, OpportunityResponse
from app.api.matches import _score_candidate
from app.core.text_preprocessing import anonymize_resume_text

router = APIRouter(prefix="/candidates", tags=["candidates"])
MAX_RESUME_BYTES = 10 * 1024 * 1024
KNOWN_SKILLS = ("python", "sql", "data analysis", "excel", "power bi", "docker", "kubernetes", "ci/cd", "linux", "aws", "terraform", "ansible", "git", "rest apis", "system design", "financial accounting", "taxation", "business analysis", "project management")


@router.get("/me/applications", response_model=list[CandidateApplicationResponse])
def candidate_applications(offset: int = Query(default=0, ge=0), limit: int = Query(default=100, ge=1, le=100), user: User = Depends(require_roles(UserRole.candidate)), db: Session = Depends(get_db)):
    rows = db.execute(select(JobApplication, JobPosting, Employer.company_name).join(Candidate, JobApplication.candidate_id == Candidate.candidate_id).join(JobPosting, JobPosting.job_id == JobApplication.job_id).join(Employer, Employer.employer_id == JobPosting.employer_id).where(Candidate.user_id == user.user_id).order_by(JobApplication.created_at.desc(), JobApplication.application_id).offset(offset).limit(limit)).all()
    return [CandidateApplicationResponse(**ApplicationResponse.model_validate(application).model_dump(), job_title=job.title, company_name=company, job_location=job.location, job_status=job.status.value) for application, job, company in rows]


def _extract_text(filename: str, content: bytes) -> str:
    suffix = Path(filename).suffix.casefold()
    if suffix == ".pdf":
        if b"%PDF-" not in content[:1024]:
            raise HTTPException(status_code=415, detail="Invalid PDF signature")
        reader = PdfReader(BytesIO(content))
        if reader.is_encrypted or len(reader.pages) > 100:
            raise HTTPException(status_code=422, detail="Resume must be unencrypted and at most 100 pages")
        return "\n".join(page.extract_text() or "" for page in reader.pages).strip()
    if suffix == ".docx":
        if not content.startswith(b"PK\x03\x04"):
            raise HTTPException(status_code=415, detail="Invalid DOCX signature")
        with ZipFile(BytesIO(content)) as archive:
            entries = archive.infolist()
            if len(entries) > 1000 or sum(entry.file_size for entry in entries) > 30 * 1024 * 1024:
                raise HTTPException(status_code=413, detail="Expanded DOCX exceeds processing limits")
            if "word/document.xml" not in archive.namelist() or any(entry.flag_bits & 1 for entry in entries):
                raise HTTPException(status_code=422, detail="Invalid or encrypted DOCX")
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
    db.add(AuditEvent(actor_user_id=user.user_id, action="profile.updated", resource_type="candidate", resource_id=candidate.candidate_id))
    db.commit()
    db.refresh(candidate)
    return candidate


@router.post("/upload-resume", response_model=CandidateProfileResponse)
@limiter.limit("5/minute")
async def upload_resume(
    request: Request,
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
        text = await run_in_threadpool(_extract_text, filename, content)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="The resume could not be read") from exc
    if not text:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="The resume contains no readable text")
    candidate.parsed_resume_text = anonymize_resume_text(text, (candidate.full_name,))[:20_000]
    candidate.skills = _skills_from_text(text)
    db.add(AuditEvent(actor_user_id=user.user_id, action="resume.parsed", resource_type="candidate", resource_id=candidate.candidate_id, details={"skills_detected": len(candidate.skills)}))
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
    eligible = []
    for job in jobs:
        result = _score_candidate(candidate, job)
        scored.append(_opportunity(job, result.final_score, activity.get(job.job_id).status if job.job_id in activity else None, employer_names.get(job.employer_id, "Workforce employer")))
        if result.hard_rule_passed:
            eligible.append(scored[-1])
    history = []
    for item in sorted(activity.values(), key=lambda value: value.updated_at, reverse=True):
        if item.job.status == JobStatus.closed or item.status in {OpportunityStatus.saved, OpportunityStatus.applied}:
            history.append(_opportunity(item.job, next((entry.match_score for entry in scored if entry.job_id == item.job_id), 0.0), item.status, employer_names.get(item.job.employer_id, "Workforce employer")))
    return CandidateDashboardResponse(
        available_opportunities=scored[:20],
        for_you=sorted(eligible, key=lambda value: value.match_score, reverse=True)[:5],
        history=history[:20],
    )


@router.post("/opportunities/{job_id}", response_model=OpportunityResponse)
def update_opportunity_status(
    job_id: UUID,
    payload: OpportunityActionRequest,
    user: User = Depends(require_roles(UserRole.candidate)),
    db: Session = Depends(get_db),
) -> OpportunityResponse:
    candidate = db.scalar(select(Candidate).where(Candidate.user_id == user.user_id))
    job = db.get(JobPosting, job_id)
    if candidate is None or job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate or job not found")
    if payload.status == OpportunityStatus.applied and job.status != JobStatus.open:
        raise HTTPException(status_code=409, detail="This job is closed")
    result = _score_candidate(candidate, job)
    if payload.status == OpportunityStatus.applied:
        if not result.hard_rule_passed:
            raise HTTPException(status_code=409, detail="Job eligibility requirements are not met")
        application_id = db.scalar(insert(JobApplication).values(candidate_id=candidate.candidate_id, job_id=job.job_id).on_conflict_do_nothing(constraint="uq_application_candidate_job").returning(JobApplication.application_id))
        if application_id:
            db.add(AuditEvent(actor_user_id=user.user_id, action="application.submitted", resource_type="application", resource_id=application_id))
    db.execute(insert(CandidateOpportunity).values(candidate_id=candidate.candidate_id, job_id=job.job_id, status=payload.status).on_conflict_do_update(constraint="uq_candidate_opportunity", set_={"status": payload.status}))
    db.commit()
    employer = db.get(Employer, job.employer_id)
    return _opportunity(job, result.final_score, payload.status, employer.company_name if employer else "Workforce employer")