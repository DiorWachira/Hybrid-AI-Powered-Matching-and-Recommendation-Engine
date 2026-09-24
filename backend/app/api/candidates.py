from io import BytesIO
from pathlib import Path
import re

from docx import Document
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.db.models import Candidate, User, UserRole
from app.db.neo4j_db import project_candidate_skills
from app.db.postgres import get_db
from app.schemas import CandidateProfileResponse, CandidateProfileUpdate

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