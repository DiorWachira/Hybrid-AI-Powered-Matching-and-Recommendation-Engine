import io
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

import rotate_demo_password
from app.db.models import AuditEvent, User, UserRole
from app.utils.security import verify_password


def _demo_user() -> User:
    return User(user_id=uuid4(), email=f"{uuid4().hex[:8]}@jobbridge.example.org", password_hash="old", role=UserRole.candidate, is_demo=True, auth_version=3)


def _run(monkeypatch, users, password):
    database = MagicMock()
    database.scalars.return_value = users
    session = MagicMock()
    session.__enter__.return_value = database
    monkeypatch.setattr(rotate_demo_password, "SessionLocal", lambda: session)
    monkeypatch.setattr("sys.argv", ["rotate_demo_password.py"])
    monkeypatch.setattr("sys.stdin", io.StringIO(password + "\n"))
    rotate_demo_password.main()
    return database


def test_demo_accounts_get_the_new_password_and_lose_their_sessions(monkeypatch, capsys):
    users = [_demo_user(), _demo_user()]
    database = _run(monkeypatch, users, "a-new-demo-password")
    for user in users:
        assert verify_password("a-new-demo-password", user.password_hash)
        assert user.auth_version == 4
    audited = [call.args[0] for call in database.add.call_args_list if isinstance(call.args[0], AuditEvent)]
    assert {event.resource_id for event in audited} == {user.user_id for user in users}
    database.commit.assert_called_once()
    assert "2 demo accounts" in capsys.readouterr().out


@pytest.mark.parametrize("password", ["too-short", "x" * 73])
def test_out_of_range_passwords_change_nothing(monkeypatch, password):
    user = _demo_user()
    with pytest.raises(SystemExit):
        _run(monkeypatch, [user], password)
    assert user.password_hash == "old" and user.auth_version == 3


def test_no_demo_accounts_changes_nothing(monkeypatch):
    with pytest.raises(SystemExit, match="No demo accounts"):
        _run(monkeypatch, [], "a-new-demo-password")
