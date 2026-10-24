from collections.abc import Callable
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db.models import User, UserRole
from app.db.postgres import get_db
from app.utils.security import ACCESS_TOKEN, MFA_ENROLLMENT_TOKEN, decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


def _authenticate(credentials: HTTPAuthorizationCredentials | None, db: Session, allowed_types: frozenset[str]) -> tuple[User, str]:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    try:
        claims = decode_access_token(credentials.credentials, allowed_types)
        user_id = UUID(claims["sub"])
    except (ValueError, KeyError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired access token") from None
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User account not found")
    if claims["ver"] != user.auth_version:
        raise HTTPException(status_code=401, detail="Session expired; sign in again")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account suspended; contact the administrator")
    return user, claims["typ"]


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    return _authenticate(credentials, db, frozenset({ACCESS_TOKEN}))[0]


def get_enrolling_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> tuple[User, bool]:
    """A signed-in user, or one holding the enrolment token that a required-MFA login returns.

    The flag is True for the enrolment token, whose holder has just proved their password.
    """
    user, token_type = _authenticate(credentials, db, frozenset({ACCESS_TOKEN, MFA_ENROLLMENT_TOKEN}))
    return user, token_type == MFA_ENROLLMENT_TOKEN


def require_roles(*roles: UserRole) -> Callable[[User], User]:
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user

    return dependency
