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


def create_access_token(user_id: UUID, role: str, auth_version: int = 0) -> str:
    settings = get_settings()
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.jwt_expire_minutes)
    return jwt.encode(
        {"sub": str(user_id), "role": role, "exp": expires_at, "ver": auth_version},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm], options={"require": ["sub", "role", "exp"]})
    except InvalidTokenError as exc:
        raise ValueError("Invalid or expired access token") from exc
    if not isinstance(payload.get("sub"), str) or not isinstance(payload.get("role"), str):
        raise ValueError("Access token is missing required claims")
    if type(payload.get("ver", 0)) is not int:
        raise ValueError("Invalid session version")
    return {"sub": payload["sub"], "role": payload["role"], "ver": payload.get("ver", 0)}
