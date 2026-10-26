from unittest.mock import MagicMock
from uuid import uuid4

import pyotp
from cryptography.fernet import Fernet

import rekey_mfa
from app.config import Settings, get_settings
from app.db.models import User, UserRole
from app.utils import mfa


def _restored_user(token: str) -> User:
    return User(user_id=uuid4(), email="admin@example.org", password_hash="x", role=UserRole.admin, mfa_secret_encrypted=token)


def _run(monkeypatch, users, argv=()):
    host_key = Fernet.generate_key().decode()
    monkeypatch.setattr(mfa, "get_settings", lambda: get_settings().model_copy(update={"mfa_encryption_key": host_key}))
    database = MagicMock()
    database.scalars.return_value = users
    session = MagicMock()
    session.__enter__.return_value = database
    monkeypatch.setattr(rekey_mfa, "SessionLocal", lambda: session)
    monkeypatch.setattr("sys.argv", ["rekey_mfa.py", *argv])
    rekey_mfa.main()
    return database


def test_development_secrets_are_reencrypted_with_the_host_key(monkeypatch, capsys):
    secret = pyotp.random_base32()
    laptop_key = Fernet(rekey_mfa.development_key(Settings.model_fields["jwt_secret"].default))
    user = _restored_user(laptop_key.encrypt(secret.encode()).decode())
    database = _run(monkeypatch, [user])
    assert mfa.decrypt_secret(user.mfa_secret_encrypted) == secret
    database.commit.assert_called_once()
    assert "1 re-encrypted, 0 already current, 0 unreadable" in capsys.readouterr().out


def test_explicit_old_key_and_unreadable_secrets(monkeypatch, capsys):
    old_key = Fernet.generate_key().decode()
    readable = _restored_user(Fernet(old_key).encrypt(b"JBSWY3DPEHPK3PXP").decode())
    foreign = _restored_user(Fernet(Fernet.generate_key()).encrypt(b"JBSWY3DPEHPK3PXP").decode())
    _run(monkeypatch, [readable, foreign], ["--old-key", old_key])
    assert mfa.decrypt_secret(readable.mfa_secret_encrypted) == "JBSWY3DPEHPK3PXP"
    output = capsys.readouterr().out
    assert "reset it with reset_mfa.py" in output
    assert "1 re-encrypted, 0 already current, 1 unreadable" in output
