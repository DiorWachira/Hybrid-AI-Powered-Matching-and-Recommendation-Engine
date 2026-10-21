from datetime import UTC, datetime, timedelta
from uuid import UUID

import bcrypt
import jwt
from jwt import InvalidTokenError

from app.config import get_settings


def hash_password(password: str) -> str:
    if len(password.encode("utf-8")) > 72:
        raise ValueError("Password must be at most 72 UTF-8 bytes")
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    if len(password.encode("utf-8")) > 72:
        return False
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


ACCESS_TOKEN = "access"
# Short-lived tokens issued after a correct password: one proves the password step before a code, the
# other lets a role that must use MFA enrol before it receives a session. Neither is a session.
MFA_CHALLENGE_TOKEN = "mfa_challenge"
MFA_ENROLLMENT_TOKEN = "mfa_enrollment"


def create_access_token(user_id: UUID, role: str, auth_version: int = 0) -> str:
    return _encode(user_id, role, auth_version, ACCESS_TOKEN, timedelta(minutes=get_settings().jwt_expire_minutes))


def create_mfa_token(user_id: UUID, role: str, auth_version: int, token_type: str) -> str:
    if token_type not in {MFA_CHALLENGE_TOKEN, MFA_ENROLLMENT_TOKEN}:
        raise ValueError("Unknown MFA token type")
    return _encode(user_id, role, auth_version, token_type, timedelta(minutes=get_settings().mfa_challenge_minutes))


def _encode(user_id: UUID, role: str, auth_version: int, token_type: str, lifetime: timedelta) -> str:
    settings = get_settings()
    return jwt.encode(
        {"sub": str(user_id), "role": role, "exp": datetime.now(UTC) + lifetime, "ver": auth_version, "typ": token_type},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str, allowed_types: frozenset[str] = frozenset({ACCESS_TOKEN})) -> dict:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm], options={"require": ["sub", "role", "exp", "typ"]})
    except InvalidTokenError as exc:
        raise ValueError("Invalid or expired access token") from exc
    if not isinstance(payload.get("sub"), str) or not isinstance(payload.get("role"), str):
        raise ValueError("Access token is missing required claims")
    if payload.get("typ") not in allowed_types:
        raise ValueError("Token cannot be used here")
    if type(payload.get("ver", 0)) is not int:
        raise ValueError("Invalid session version")
    return {"sub": payload["sub"], "role": payload["role"], "ver": payload.get("ver", 0), "typ": payload["typ"]}
