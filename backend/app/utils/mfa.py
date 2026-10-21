"""Authenticator-app (RFC 6238 TOTP) second factor, recovery codes and lockout."""
from __future__ import annotations

import base64
import hashlib
import hmac
import io
import secrets
import time
from datetime import UTC, datetime, timedelta

import pyotp
import segno
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import MfaRecoveryCode, User

TOTP_STEP_SECONDS = 30
# Accept the previous and next step as well, to tolerate phone clock drift of about 30 seconds.
TOTP_DRIFT_STEPS = 1
RECOVERY_CODE_COUNT = 10
RECOVERY_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"
MAX_FAILED_ATTEMPTS = 5
LOCKOUT = timedelta(minutes=15)


class MfaLocked(Exception):
    def __init__(self, until: datetime):
        super().__init__("Too many incorrect codes")
        self.until = until


def _fernet() -> Fernet:
    settings = get_settings()
    if settings.mfa_encryption_key:
        return Fernet(settings.mfa_encryption_key)
    # Development only (config refuses shared deployments without a key). Rotating JWT_SECRET here
    # makes existing enrolments unreadable, so affected users would need an MFA reset.
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(b"jobbridge-mfa:" + settings.jwt_secret.encode()).digest()))


def encrypt_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode()).decode()


def decrypt_secret(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Stored MFA secret cannot be decrypted with the configured key") from exc


def new_secret() -> str:
    return pyotp.random_base32()


def provisioning_uri(secret: str, email: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=get_settings().mfa_issuer)


def qr_svg_data_uri(uri: str) -> str:
    buffer = io.BytesIO()
    segno.make(uri, error="m").save(buffer, kind="svg", scale=5, border=2, dark="#111827", light="#ffffff", xmldecl=False)
    return "data:image/svg+xml;base64," + base64.b64encode(buffer.getvalue()).decode()


def matching_step(secret: str, code: str, last_used_step: int | None, now: float | None = None) -> int | None:
    """Return the time step a 6-digit code belongs to, or None if it is wrong or already used."""
    if len(code) != 6 or not code.isdigit():
        return None
    totp = pyotp.TOTP(secret)
    current = int((time.time() if now is None else now) // TOTP_STEP_SECONDS)
    for step in range(current - TOTP_DRIFT_STEPS, current + TOTP_DRIFT_STEPS + 1):
        if hmac.compare_digest(totp.at(step * TOTP_STEP_SECONDS), code):
            return step if last_used_step is None or step > last_used_step else None
    return None


def normalize_recovery_code(code: str) -> str:
    return "".join(character for character in code.lower() if character.isalnum())


def hash_recovery_code(code: str) -> str:
    return hashlib.sha256(normalize_recovery_code(code).encode()).hexdigest()


def replace_recovery_codes(db: Session, user: User) -> list[str]:
    db.execute(delete(MfaRecoveryCode).where(MfaRecoveryCode.user_id == user.user_id))
    codes = []
    for _ in range(RECOVERY_CODE_COUNT):
        raw = "".join(secrets.choice(RECOVERY_ALPHABET) for _ in range(10))
        codes.append(f"{raw[:5]}-{raw[5:]}")
        db.add(MfaRecoveryCode(user_id=user.user_id, code_hash=hash_recovery_code(raw)))
    return codes


def clear_mfa(db: Session, user: User) -> None:
    user.mfa_secret_encrypted = None
    user.mfa_enabled_at = None
    user.mfa_last_used_step = None
    user.mfa_failed_attempts = 0
    user.mfa_locked_until = None
    db.execute(delete(MfaRecoveryCode).where(MfaRecoveryCode.user_id == user.user_id))


def is_required(user: User) -> bool:
    return user.role.value in get_settings().mfa_required_roles


def check_second_factor(db: Session, user: User, code: str, *, allow_recovery: bool, pending: bool = False) -> str | None:
    """Verify a TOTP or recovery code for a row locked by the caller.

    Returns "totp" or "recovery" on success and None on failure. Failures count towards a lockout
    that also covers recovery codes, so neither can be guessed faster than five tries per 15 minutes.
    The caller commits either way, so failure counts persist.
    """
    now = datetime.now(UTC)
    if user.mfa_locked_until is not None and user.mfa_locked_until > now:
        raise MfaLocked(user.mfa_locked_until)
    if user.mfa_secret_encrypted is None or (user.mfa_enabled_at is None) != pending:
        return None
    method = None
    compact = code.strip().replace(" ", "")
    step = matching_step(decrypt_secret(user.mfa_secret_encrypted), compact, user.mfa_last_used_step)
    if step is not None:
        user.mfa_last_used_step = step
        method = "totp"
    elif allow_recovery and len(normalize_recovery_code(compact)) == 10:
        consumed = db.execute(
            update(MfaRecoveryCode)
            .where(MfaRecoveryCode.user_id == user.user_id, MfaRecoveryCode.code_hash == hash_recovery_code(compact), MfaRecoveryCode.used_at.is_(None))
            .values(used_at=now)
        )
        if consumed.rowcount == 1:
            method = "recovery"
    if method is None:
        user.mfa_failed_attempts += 1
        if user.mfa_failed_attempts >= MAX_FAILED_ATTEMPTS:
            user.mfa_failed_attempts = 0
            user.mfa_locked_until = now + LOCKOUT
        return None
    user.mfa_failed_attempts = 0
    user.mfa_locked_until = None
    return method


def remaining_recovery_codes(db: Session, user: User) -> int:
    return db.scalar(select(func.count()).select_from(MfaRecoveryCode).where(MfaRecoveryCode.user_id == user.user_id, MfaRecoveryCode.used_at.is_(None))) or 0
