from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import User, UserRole
from app.db.postgres import get_db
from app.main import app
from app.utils import google_identity
from app.utils.security import decode_access_token

CLIENT_ID = "test-client.apps.googleusercontent.com"
ALLOWED = "allowed@gmail.com"
SIGNING_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _token(email=ALLOWED, *, key=SIGNING_KEY, audience=CLIENT_ID, issuer="https://accounts.google.com", verified=True, expires_in=600) -> str:
    now = datetime.now(UTC)
    claims = {"iss": issuer, "aud": audience, "sub": "1234567890", "email": email, "email_verified": verified, "iat": now, "exp": now + timedelta(seconds=expires_in)}
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test-key"})


def _user(role=UserRole.candidate, email=ALLOWED, mfa_enabled=False) -> User:
    return User(user_id=uuid4(), email=email, password_hash="unused", role=role, is_active=True, auth_version=0, mfa_failed_attempts=0,
                mfa_enabled_at=datetime.now(UTC) if mfa_enabled else None)


@pytest.fixture
def client(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "google_client_id", CLIENT_ID)
    monkeypatch.setattr(settings, "google_signin_emails", [" Allowed@Gmail.com "])
    def google_key(token):
        # Stand in for Google's published keys: the test key is the only one "Google" signs with.
        jwt.get_unverified_header(token)  # malformed tokens fail here, as with the real key client
        return SimpleNamespace(key=SIGNING_KEY.public_key())
    monkeypatch.setattr(google_identity._keys, "get_signing_key_from_jwt", google_key)
    database = MagicMock(spec=Session)
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: database
    with TestClient(app) as test_client:
        yield test_client, database
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)


def test_options_expose_client_id_only_when_enabled(client, monkeypatch):
    test_client, _ = client
    assert test_client.get("/api/auth/google").json() == {"client_id": CLIENT_ID}
    monkeypatch.setattr(get_settings(), "google_client_id", "")
    assert test_client.get("/api/auth/google").json() == {"client_id": None}
    assert test_client.post("/api/auth/google", json={"credential": _token()}).status_code == 404


@pytest.mark.parametrize("role", [UserRole.candidate, UserRole.recruiter])
def test_allowlisted_account_signs_in(client, role):
    test_client, database = client
    user = _user(role)
    database.scalar.return_value = user
    response = test_client.post("/api/auth/google", json={"credential": _token()})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "authenticated" and body["role"] == role.value
    assert decode_access_token(body["access_token"])["sub"] == str(user.user_id)
    assert database.add.call_args.args[0].details == {"method": "google"}
    database.commit.assert_called_once()


def test_two_step_verification_still_applies(client):
    test_client, database = client
    database.scalar.return_value = _user(mfa_enabled=True)
    body = test_client.post("/api/auth/google", json={"credential": _token()}).json()
    assert body["status"] == "mfa_required" and body["access_token"] is None and body["challenge_token"]
    database.commit.assert_not_called()


@pytest.mark.parametrize("credential", [
    _token(key=OTHER_KEY),
    _token(audience="someone-else.apps.googleusercontent.com"),
    _token(issuer="https://evil.example.com"),
    _token(expires_in=-120),
    _token(verified=False),
    "not-a-token",
])
def test_invalid_google_tokens_are_rejected(client, credential):
    test_client, database = client
    database.scalar.return_value = _user()
    assert test_client.post("/api/auth/google", json={"credential": credential}).status_code == 401
    database.commit.assert_not_called()


@pytest.mark.parametrize("email,account", [
    ("stranger@gmail.com", lambda: _user(email="stranger@gmail.com")),  # valid Google account, not on the allowlist
    (ALLOWED, lambda: None),  # allowlisted but has no JobBridge account: register with a password instead
    (ALLOWED, lambda: _user(UserRole.admin)),  # administrators always use password and MFA
])
def test_only_existing_allowlisted_non_admin_accounts_may_use_google(client, email, account):
    test_client, database = client
    database.scalar.return_value = account()
    response = test_client.post("/api/auth/google", json={"credential": _token(email)})
    assert response.status_code == 403
    assert "use your email and password" in response.json()["detail"]
    database.commit.assert_not_called()


def test_google_outage_reports_unavailable(client, monkeypatch):
    test_client, database = client

    def unreachable(token):
        raise jwt.PyJWKClientConnectionError("network down")
    monkeypatch.setattr(google_identity._keys, "get_signing_key_from_jwt", unreachable)
    assert test_client.post("/api/auth/google", json={"credential": _token()}).status_code == 503
    database.commit.assert_not_called()
