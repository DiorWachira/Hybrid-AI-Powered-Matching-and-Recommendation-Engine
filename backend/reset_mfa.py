"""Turn off two-step verification for an account, e.g. an administrator who lost their phone.

Run on the server: shell access is the recovery trust root. The account signs in with its password
next time; roles that require MFA are sent straight back through enrolment.
"""
from __future__ import annotations

import argparse

from pydantic import EmailStr, TypeAdapter
from sqlalchemy import select

from app.db.models import AuditEvent, User
from app.db.postgres import SessionLocal
from app.utils.mfa import clear_mfa


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("email")
    parser.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    args = parser.parse_args()
    email = str(TypeAdapter(EmailStr).validate_python(args.email)).lower()
    with SessionLocal() as db:
        account = db.scalar(select(User).where(User.email == email).with_for_update())
        if account is None:
            raise SystemExit("No account with that email; nothing changed")
        if account.mfa_secret_encrypted is None:
            raise SystemExit("That account does not use two-step verification; nothing changed")
        if not args.yes and input(f"Reset two-step verification for {email} ({account.role.value})? Type 'reset' to confirm: ").strip() != "reset":
            raise SystemExit("Cancelled; nothing changed")
        clear_mfa(db, account)
        account.auth_version += 1
        db.add(AuditEvent(actor_user_id=None, action="account.mfa_reset_cli", resource_type="user", resource_id=account.user_id))
        db.commit()
    print(f"Two-step verification reset for {email}; existing sessions were signed out.")


if __name__ == "__main__":
    main()
