import hashlib
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from app.core.rate_limit import limiter
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_enrolling_user
from app.config import get_settings
from app.db.models import AuditEvent, Candidate, Employer, User, UserRole
from app.db.postgres import get_db
from app.schemas import (GoogleLoginRequest, GoogleSignInOptions, LoginRequest, LoginResponse, MfaCodeRequest, MfaConfirmRequest, MfaEnableResponse, MfaSetupRequest, MfaSetupResponse,
                         MfaVerifyRequest, PasswordResetRequest, ProfileResponse, RecoveryCodesResponse, RegisterRequest, TokenResponse)
from app.utils import google_identity, mfa
from app.utils.security import (MFA_CHALLENGE_TOKEN, MFA_ENROLLMENT_TOKEN, create_access_token, create_mfa_token, decode_access_token,
                                hash_password, verify_password)

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
def register(request: Request, payload: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
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

    return TokenResponse(access_token=create_access_token(user.user_id, user.role.value, user.auth_version), role=user.role)


@router.post("/login", response_model=LoginResponse)
@limiter.limit("10/minute")
def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    user = db.scalar(select(User).where(User.email == str(payload.email).lower()))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    return _first_factor_passed(db, user)


def _first_factor_passed(db: Session, user: User, details: dict | None = None) -> LoginResponse:
    """Finish a sign-in whose first factor (password or Google) succeeded; two-step verification still applies."""
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account suspended; contact the administrator")
    if user.mfa_enabled_at is not None:
        return LoginResponse(status="mfa_required", role=user.role, challenge_token=create_mfa_token(user.user_id, user.role.value, user.auth_version, MFA_CHALLENGE_TOKEN))
    if mfa.is_required(user):
        return LoginResponse(status="mfa_setup_required", role=user.role, challenge_token=create_mfa_token(user.user_id, user.role.value, user.auth_version, MFA_ENROLLMENT_TOKEN))
    db.add(AuditEvent(actor_user_id=user.user_id, action="account.login", resource_type="user", resource_id=user.user_id, details=details))
    db.commit()
    return LoginResponse(status="authenticated", role=user.role, access_token=create_access_token(user.user_id, user.role.value, user.auth_version))


@router.get("/google", response_model=GoogleSignInOptions)
def google_sign_in_options() -> GoogleSignInOptions:
    """The OAuth client ID the sign-in page needs to show the Google button, or null when it is switched off."""
    return GoogleSignInOptions(client_id=get_settings().google_client_id or None)


@router.post("/google", response_model=LoginResponse)
@limiter.limit("10/minute")
def google_login(request: Request, payload: GoogleLoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    settings = get_settings()
    if not settings.google_client_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Google sign-in is not enabled")
    try:
        email = google_identity.verified_email(payload.credential, settings.google_client_id)
    except google_identity.GoogleUnavailable:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Google sign-in is temporarily unavailable; use your password") from None
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google sign-in could not be verified") from None
    user = db.scalar(select(User).where(User.email == email))
    # One message for every refusal, so the endpoint does not reveal which emails have accounts.
    if email not in {item.strip().lower() for item in settings.google_signin_emails} or user is None or user.role == UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This Google account cannot sign in here; use your email and password")
    return _first_factor_passed(db, user, {"method": "google"})


def _locked(until: datetime) -> HTTPException:
    minutes = max(1, round((until - datetime.now(UTC)).total_seconds() / 60))
    return HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f"Too many incorrect codes; try again in {minutes} minute{'' if minutes == 1 else 's'}")


def _check_code(db: Session, user: User, code: str, *, allow_recovery: bool, pending: bool = False, failure_status: int = status.HTTP_401_UNAUTHORIZED) -> str:
    try:
        method = mfa.check_second_factor(db, user, code, allow_recovery=allow_recovery, pending=pending)
    except mfa.MfaLocked as locked:
        raise _locked(locked.until) from None
    if method is None:
        # Commit the failure count before refusing, so the lockout survives the error response.
        db.add(AuditEvent(actor_user_id=user.user_id, action="account.mfa_failed", resource_type="user", resource_id=user.user_id))
        db.commit()
        if user.mfa_locked_until is not None:
            raise _locked(user.mfa_locked_until)
        raise HTTPException(status_code=failure_status, detail="Incorrect or already used code")
    return method


@router.post("/mfa/verify", response_model=TokenResponse)
@limiter.limit("5/minute")
def verify_mfa(request: Request, payload: MfaVerifyRequest, db: Session = Depends(get_db)) -> TokenResponse:
    expired = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign-in step expired; enter your password again")
    try:
        claims = decode_access_token(payload.challenge_token, frozenset({MFA_CHALLENGE_TOKEN}))
        user_id = UUID(claims["sub"])
    except (ValueError, KeyError):
        raise expired from None
    user = db.scalar(select(User).where(User.user_id == user_id).with_for_update())
    if user is None or claims["ver"] != user.auth_version or not user.is_active or user.mfa_enabled_at is None:
        raise expired
    method = _check_code(db, user, payload.code, allow_recovery=True)
    db.add(AuditEvent(actor_user_id=user.user_id, action="account.login", resource_type="user", resource_id=user.user_id, details={"mfa": method}))
    db.commit()
    return TokenResponse(access_token=create_access_token(user.user_id, user.role.value, user.auth_version), role=user.role)


@router.post("/mfa/setup", response_model=MfaSetupResponse)
@limiter.limit("10/minute")
def start_mfa_setup(request: Request, payload: MfaSetupRequest, enrolling: tuple[User, bool] = Depends(get_enrolling_user), db: Session = Depends(get_db)) -> MfaSetupResponse:
    user, via_enrollment_token = enrolling
    if not via_enrollment_token and (payload.password is None or not verify_password(payload.password, user.password_hash)):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Password is incorrect")
    if user.mfa_enabled_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Two-step verification is already on")
    secret = mfa.new_secret()
    user.mfa_secret_encrypted = mfa.encrypt_secret(secret)
    user.mfa_last_used_step = None
    db.commit()
    uri = mfa.provisioning_uri(secret, user.email)
    return MfaSetupResponse(secret=secret, otpauth_uri=uri, qr_svg=mfa.qr_svg_data_uri(uri))


@router.post("/mfa/enable", response_model=MfaEnableResponse)
@limiter.limit("10/minute")
def enable_mfa(request: Request, payload: MfaCodeRequest, enrolling: tuple[User, bool] = Depends(get_enrolling_user), db: Session = Depends(get_db)) -> MfaEnableResponse:
    user, via_enrollment_token = enrolling
    if user.mfa_enabled_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Two-step verification is already on")
    if user.mfa_secret_encrypted is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Start setup before confirming a code")
    _check_code(db, user, payload.code, allow_recovery=False, pending=True, failure_status=status.HTTP_400_BAD_REQUEST)
    user.mfa_enabled_at = datetime.now(UTC)
    # Signs out every other session, including ones opened before the second factor existed.
    user.auth_version += 1
    codes = mfa.replace_recovery_codes(db, user)
    db.add(AuditEvent(actor_user_id=user.user_id, action="account.mfa_enabled", resource_type="user", resource_id=user.user_id, details={"enforced": via_enrollment_token}))
    db.commit()
    return MfaEnableResponse(access_token=create_access_token(user.user_id, user.role.value, user.auth_version), role=user.role, recovery_codes=codes)


def _confirm_identity(db: Session, user: User, payload: MfaConfirmRequest) -> None:
    if user.mfa_enabled_at is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Two-step verification is not on")
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Password is incorrect")
    _check_code(db, user, payload.code, allow_recovery=True)


@router.post("/mfa/disable", response_model=TokenResponse)
@limiter.limit("5/minute")
def disable_mfa(request: Request, payload: MfaConfirmRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> TokenResponse:
    if mfa.is_required(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Your account type must keep two-step verification on")
    _confirm_identity(db, user, payload)
    mfa.clear_mfa(db, user)
    user.auth_version += 1
    db.add(AuditEvent(actor_user_id=user.user_id, action="account.mfa_disabled", resource_type="user", resource_id=user.user_id))
    db.commit()
    return TokenResponse(access_token=create_access_token(user.user_id, user.role.value, user.auth_version), role=user.role)


@router.post("/mfa/recovery-codes", response_model=RecoveryCodesResponse)
@limiter.limit("5/minute")
def regenerate_recovery_codes(request: Request, payload: MfaConfirmRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> RecoveryCodesResponse:
    _confirm_identity(db, user, payload)
    codes = mfa.replace_recovery_codes(db, user)
    db.add(AuditEvent(actor_user_id=user.user_id, action="account.mfa_recovery_regenerated", resource_type="user", resource_id=user.user_id))
    db.commit()
    return RecoveryCodesResponse(recovery_codes=codes)


@router.post("/reset-password")
@limiter.limit("10/minute")
def reset_password(request: Request, payload: PasswordResetRequest, db: Session = Depends(get_db)):
    digest = hashlib.sha256(payload.token.encode()).hexdigest()
    user = db.scalar(select(User).where(User.password_reset_hash == digest, User.password_reset_expires_at > datetime.now(UTC)).with_for_update())
    if user is None or not user.is_active:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    user.password_hash = hash_password(payload.new_password)
    user.password_reset_hash = None
    user.password_reset_expires_at = None
    user.auth_version += 1
    db.add(AuditEvent(actor_user_id=user.user_id, action="account.password_reset", resource_type="user", resource_id=user.user_id))
    db.commit()
    return {"message": "Password updated. Sign in with your new password."}


@router.get("/me", response_model=ProfileResponse)
def read_current_profile(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ProfileResponse:
    enabled = user.mfa_enabled_at is not None
    display_name = company_name = None
    if user.role == UserRole.candidate:
        display_name = db.scalar(select(Candidate.full_name).where(Candidate.user_id == user.user_id))
    elif user.role == UserRole.recruiter:
        employer = db.execute(select(Employer.contact_name, Employer.company_name).where(Employer.user_id == user.user_id)).first()
        if employer:
            display_name, company_name = employer
    return ProfileResponse(user_id=user.user_id, email=user.email, role=user.role, display_name=display_name, company_name=company_name,
                           mfa_enabled=enabled, mfa_required=mfa.is_required(user),
                           mfa_recovery_codes_remaining=mfa.remaining_recovery_codes(db, user) if enabled else 0)
