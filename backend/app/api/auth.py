from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.models import AuditEvent, Candidate, Employer, User, UserRole
from app.db.postgres import get_db
from app.schemas import LoginRequest, ProfileResponse, RegisterRequest, TokenResponse
from app.utils.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    if payload.role == UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator accounts must be created by the administrator bootstrap command")
    if payload.role == UserRole.candidate and not payload.full_name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Candidate registration requires full_name")
    if payload.role == UserRole.recruiter and not payload.company_name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Recruiter registration requires company_name")

    user = User(email=str(payload.email).lower(), password_hash=hash_password(payload.password), role=payload.role)
    db.add(user)
    try:
        db.flush()
        if payload.role == UserRole.candidate:
            db.add(Candidate(user_id=user.user_id, full_name=payload.full_name or "", location=payload.location))
        elif payload.role == UserRole.recruiter:
            db.add(Employer(user_id=user.user_id, company_name=payload.company_name or "", contact_name=payload.full_name, industry=payload.industry, location=payload.location))
        db.add(AuditEvent(actor_user_id=user.user_id, action="account.registered", resource_type="user", resource_id=user.user_id, details={"role": user.role.value}))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email address is already registered") from None

    return TokenResponse(access_token=create_access_token(user.user_id, user.role.value), role=user.role)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == str(payload.email).lower()))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account suspended; contact the administrator")
    db.add(AuditEvent(actor_user_id=user.user_id, action="account.login", resource_type="user", resource_id=user.user_id))
    db.commit()
    return TokenResponse(access_token=create_access_token(user.user_id, user.role.value), role=user.role)


@router.get("/me", response_model=ProfileResponse)
def read_current_profile(user: User = Depends(get_current_user)) -> ProfileResponse:
    return ProfileResponse(user_id=user.user_id, email=user.email, role=user.role)
