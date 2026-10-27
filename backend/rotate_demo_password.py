"""Give every demo account (is_demo) a new password and sign out their existing sessions.

Run on the server through `deploy/jb demo-password`, which reads the password without echo and pipes
it in on standard input. Run directly in a terminal, it prompts for the password itself.
"""
from __future__ import annotations

import argparse
import sys
from getpass import getpass

from sqlalchemy import select

from app.db.models import AuditEvent, User
from app.db.postgres import SessionLocal
from app.utils.security import hash_password


def read_password() -> str:
    if not sys.stdin.isatty():
        return sys.stdin.readline().rstrip("\r\n")
    password = getpass("New demo-account password (minimum 12 characters): ")
    if getpass("Repeat it: ") != password:
        raise SystemExit("Passwords did not match; nothing changed")
    return password


def main() -> None:
    argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
    password = read_password()
    if len(password) < 12 or len(password.encode("utf-8")) > 72:
        raise SystemExit("Password must contain at least 12 characters and at most 72 UTF-8 bytes; nothing changed")
    # Every demo account shares the password, so one bcrypt hash serves them all and keeps this fast.
    password_hash = hash_password(password)
    with SessionLocal() as db:
        accounts = list(db.scalars(select(User).where(User.is_demo.is_(True)).with_for_update()))
        if not accounts:
            raise SystemExit("No demo accounts found; nothing changed")
        for account in accounts:
            account.password_hash = password_hash
            account.auth_version += 1
            db.add(AuditEvent(actor_user_id=None, action="account.demo_password_rotated_cli", resource_type="user", resource_id=account.user_id))
        db.commit()
    print(f"Updated the password of {len(accounts)} demo accounts; their existing sessions were signed out.")


if __name__ == "__main__":
    main()
