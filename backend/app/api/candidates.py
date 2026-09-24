from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.db.models import Candidate, User, UserRole
from app.db.postgres import get_db
from app.schemas import CandidateProfileResponse, CandidateProfileUpdate

router = APIRouter(prefix="/candidates", tags=["candidates"])


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