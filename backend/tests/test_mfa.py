from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

import jwt
import pyotp
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.config import get_settings
from app.db.models import User, UserRole
from app.db.postgres import get_db
from app.main import app
from app.utils import mfa
from app.utils.security import MFA_CHALLENGE_TOKEN, MFA_ENROLLMENT_TOKEN, create_access_token, create_mfa_token, hash_password

PASSWORD = "correct horse battery"


def _user(role=UserRole.candidate, secret: str | None = None, enabled=True) -> User:
    account = User(user_id=uuid4(), email=f"{role.value}@example.org", password_hash=hash_password(PASSWORD), role=role,
                   is_active=True, auth_version=0, mfa_failed_attempts=0)
    if secret:
        account.mfa_secret_encrypted = mfa.encrypt_secret(secret)
        account.mfa_enabled_at = datetime.now(UTC) if enabled else None
    return account


def _wrong_code(secret: str) -> str:
    valid = {pyotp.TOTP(secret).at(datetime.now(UTC) + timedelta(seconds=offset)) for offset in (-30, 0, 30)}
    return next(code for code in ("000000", "111111", "222222", "333333") if code not in valid)


@pytest.fixture
def client():
    database = MagicMock(spec=Session)
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: database
    with TestClient(app) as test_client:
        yield test_client, database
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)


def test_totp_accepts_one_step_of_drift_and_rejects_replay():
    secret = pyotp.random_base32()
    now = 1_800_000_000.0
    step = int(now // 30)
    totp = pyotp.TOTP(secret)
    assert mfa.matching_step(secret, totp.at(now), None, now) == step
    assert mfa.matching_step(secret, totp.at(now - 30), None, now) == step - 1
    assert mfa.matching_step(secret, totp.at(now + 30), None, now) == step + 1
    assert mfa.matching_step(secret, totp.at(now - 90), None, now) is None
    assert mfa.matching_step(secret, totp.at(now), step, now) is None
    assert mfa.matching_step(secret, "12a456", None, now) is None


def test_stored_secret_is_encrypted():
    secret = pyotp.random_base32()
    stored = mfa.encrypt_secret(secret)
    assert secret not in stored
    assert mfa.decrypt_secret(stored) == secret


def test_lockout_after_five_wrong_codes_blocks_valid_codes():
    secret = pyotp.random_base32()
    account = _user(secret=secret)
    database = MagicMock(spec=Session)
    for _ in range(mfa.MAX_FAILED_ATTEMPTS):
        assert mfa.check_second_factor(database, account, _wrong_code(secret), allow_recovery=False) is None
    assert account.mfa_locked_until > datetime.now(UTC)
    with pytest.raises(mfa.MfaLocked):
        mfa.check_second_factor(database, account, pyotp.TOTP(secret).now(), allow_recovery=False)


def test_recovery_code_is_consumed_through_a_single_use_update():
    secret = pyotp.random_base32()
    account = _user(secret=secret)
    database = MagicMock(spec=Session)
    database.execute.return_value.rowcount = 1
    assert mfa.check_second_factor(database, account, "ABCDE-FGHJK", allow_recovery=True) == "recovery"
    statement = database.execute.call_args.args[0]
    assert "used_at IS NULL" in str(statement.compile())
    database.execute.return_value.rowcount = 0
    assert mfa.check_second_factor(database, account, "abcde-fghjk", allow_recovery=True) is None


def test_recovery_codes_are_stored_only_as_hashes():
    database = MagicMock(spec=Session)
    codes = mfa.replace_recovery_codes(database, _user())
    stored = [call.args[0].code_hash for call in database.add.call_args_list]
    assert len(codes) == len(set(codes)) == mfa.RECOVERY_CODE_COUNT
    assert stored == [mfa.hash_recovery_code(code) for code in codes]
    assert not set(codes) & set(stored)


def test_login_without_mfa_returns_session_for_optional_roles(client):
    test_client, database = client
    database.scalar.return_value = _user(UserRole.candidate)
    body = test_client.post("/api/auth/login", json={"email": "candidate@example.org", "password": PASSWORD}).json()
    assert body["status"] == "authenticated" and body["access_token"] and body["challenge_token"] is None


def test_admin_without_mfa_must_enrol_and_enrolment_token_is_not_a_session(client):
    test_client, database = client
    admin = _user(UserRole.admin)
    database.scalar.return_value = admin
    body = test_client.post("/api/auth/login", json={"email": "admin@example.org", "password": PASSWORD}).json()
    assert body["status"] == "mfa_setup_required" and body["access_token"] is None
    database.get.return_value = admin
    assert test_client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['challenge_token']}"}).status_code == 401
    setup = test_client.post("/api/auth/mfa/setup", json={}, headers={"Authorization": f"Bearer {body['challenge_token']}"})
    assert setup.status_code == 200
    assert setup.json()["qr_svg"].startswith("data:image/svg+xml;base64,")
    assert setup.json()["otpauth_uri"].startswith("otpauth://totp/JobBridge:")
    assert mfa.decrypt_secret(admin.mfa_secret_encrypted) == setup.json()["secret"]
    assert admin.mfa_enabled_at is None


def test_enable_confirms_code_rotates_sessions_and_returns_recovery_codes(client):
    test_client, database = client
    secret = pyotp.random_base32()
    admin = _user(UserRole.admin, secret=secret, enabled=False)
    database.get.return_value = admin
    token = create_mfa_token(admin.user_id, "admin", 0, MFA_ENROLLMENT_TOKEN)
    rejected = test_client.post("/api/auth/mfa/enable", json={"code": _wrong_code(secret)}, headers={"Authorization": f"Bearer {token}"})
    assert rejected.status_code == 400 and admin.mfa_enabled_at is None
    response = test_client.post("/api/auth/mfa/enable", json={"code": pyotp.TOTP(secret).now()}, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert admin.mfa_enabled_at is not None and admin.auth_version == 1
    assert len(response.json()["recovery_codes"]) == mfa.RECOVERY_CODE_COUNT
    assert jwt.decode(response.json()["access_token"], get_settings().jwt_secret, algorithms=[get_settings().jwt_algorithm])["ver"] == 1


def test_session_enrolment_requires_the_password(client):
    test_client, database = client
    account = _user(UserRole.recruiter)
    database.get.return_value = account
    headers = {"Authorization": f"Bearer {create_access_token(account.user_id, 'recruiter', 0)}"}
    assert test_client.post("/api/auth/mfa/setup", json={}, headers=headers).status_code == 401
    assert test_client.post("/api/auth/mfa/setup", json={"password": "wrong password"}, headers=headers).status_code == 401
    assert test_client.post("/api/auth/mfa/setup", json={"password": PASSWORD}, headers=headers).status_code == 200


def test_login_with_mfa_needs_a_fresh_code(client):
    test_client, database = client
    secret = pyotp.random_base32()
    account = _user(UserRole.recruiter, secret=secret)
    database.scalar.return_value = account
    body = test_client.post("/api/auth/login", json={"email": "recruiter@example.org", "password": PASSWORD}).json()
    assert body["status"] == "mfa_required" and body["access_token"] is None
    code = pyotp.TOTP(secret).now()
    verified = test_client.post("/api/auth/mfa/verify", json={"challenge_token": body["challenge_token"], "code": code})
    assert verified.status_code == 200 and verified.json()["access_token"]
    replay = test_client.post("/api/auth/mfa/verify", json={"challenge_token": body["challenge_token"], "code": code})
    assert replay.status_code == 401


def test_verify_locks_after_repeated_wrong_codes(client):
    test_client, database = client
    secret = pyotp.random_base32()
    account = _user(UserRole.candidate, secret=secret)
    database.scalar.return_value = account
    challenge = create_mfa_token(account.user_id, "candidate", 0, MFA_CHALLENGE_TOKEN)
    statuses = [test_client.post("/api/auth/mfa/verify", json={"challenge_token": challenge, "code": _wrong_code(secret)}) for _ in range(mfa.MAX_FAILED_ATTEMPTS)]
    assert [response.status_code for response in statuses] == [401] * 4 + [429]
    assert "Too many incorrect codes" in statuses[-1].json()["detail"]


@pytest.mark.parametrize("token_type", [MFA_ENROLLMENT_TOKEN, "access"])
def test_verify_rejects_tokens_other_than_a_challenge(client, token_type):
    test_client, database = client
    secret = pyotp.random_base32()
    account = _user(secret=secret)
    database.scalar.return_value = account
    token = create_access_token(account.user_id, "candidate", 0) if token_type == "access" else create_mfa_token(account.user_id, "candidate", 0, token_type)
    assert test_client.post("/api/auth/mfa/verify", json={"challenge_token": token, "code": pyotp.TOTP(secret).now()}).status_code == 401


def test_challenge_is_void_after_a_session_revocation(client):
    test_client, database = client
    secret = pyotp.random_base32()
    account = _user(secret=secret)
    challenge = create_mfa_token(account.user_id, "candidate", 0, MFA_CHALLENGE_TOKEN)
    account.auth_version = 1
    database.scalar.return_value = account
    assert test_client.post("/api/auth/mfa/verify", json={"challenge_token": challenge, "code": pyotp.TOTP(secret).now()}).status_code == 401


def test_untyped_legacy_tokens_are_rejected(client):
    test_client, database = client
    account = _user()
    database.get.return_value = account
    settings = get_settings()
    legacy = jwt.encode({"sub": str(account.user_id), "role": "candidate", "exp": datetime.now(UTC) + timedelta(minutes=5), "ver": 0}, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    assert test_client.get("/api/auth/me", headers={"Authorization": f"Bearer {legacy}"}).status_code == 401


def test_required_role_cannot_disable_mfa(client):
    test_client, _ = client
    admin = _user(UserRole.admin, secret=pyotp.random_base32())
    app.dependency_overrides[get_current_user] = lambda: admin
    response = test_client.post("/api/auth/mfa/disable", json={"password": PASSWORD, "code": "123456"})
    assert response.status_code == 403 and admin.mfa_enabled_at is not None


def test_optional_role_disables_with_password_and_code(client):
    test_client, database = client
    secret = pyotp.random_base32()
    account = _user(UserRole.candidate, secret=secret)
    app.dependency_overrides[get_current_user] = lambda: account
    assert test_client.post("/api/auth/mfa/disable", json={"password": "wrong password", "code": pyotp.TOTP(secret).now()}).status_code == 401
    response = test_client.post("/api/auth/mfa/disable", json={"password": PASSWORD, "code": pyotp.TOTP(secret).now()})
    assert response.status_code == 200
    assert account.mfa_secret_encrypted is None and account.mfa_enabled_at is None and account.auth_version == 1


def test_admin_cannot_reset_another_administrators_mfa_from_the_dashboard(client):
    test_client, database = client
    admin = _user(UserRole.admin, secret=pyotp.random_base32())
    other_admin = _user(UserRole.admin, secret=pyotp.random_base32())
    app.dependency_overrides[get_current_user] = lambda: admin
    database.scalar.return_value = other_admin
    response = test_client.post(f"/api/admin/users/{other_admin.user_id}/mfa-reset", json={"password": PASSWORD})
    assert response.status_code == 409 and other_admin.mfa_enabled_at is not None


def test_admin_resets_a_users_mfa_and_signs_them_out(client):
    test_client, database = client
    admin = _user(UserRole.admin, secret=pyotp.random_base32())
    account = _user(UserRole.recruiter, secret=pyotp.random_base32())
    app.dependency_overrides[get_current_user] = lambda: admin
    database.scalar.return_value = account
    assert test_client.post(f"/api/admin/users/{account.user_id}/mfa-reset", json={"password": "wrong password"}).status_code == 401
    assert test_client.post(f"/api/admin/users/{account.user_id}/mfa-reset", json={"password": PASSWORD}).status_code == 200
    assert account.mfa_secret_encrypted is None and account.auth_version == 1
