"""Create an administrator account for a local deployment."""
from __future__ import annotations

import argparse
import os
import secrets
import subprocess
import tempfile
from getpass import getpass
from pathlib import Path

from pydantic import EmailStr, TypeAdapter
from sqlalchemy import select

from app.db.models import AuditEvent, User, UserRole
from app.db.postgres import SessionLocal
from app.utils.security import hash_password


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("email")
    parser.add_argument("--generate-password", action="store_true", help="save a random password in a private directory outside the repository")
    args = parser.parse_args()
    email = str(TypeAdapter(EmailStr).validate_python(args.email)).lower()
    password = secrets.token_urlsafe(30) if args.generate_password else getpass("Administrator password (minimum 12 characters): ")
    if len(password) < 12 or len(password.encode("utf-8")) > 72:
        raise SystemExit("Password must contain at least 12 characters and at most 72 UTF-8 bytes")
    credential_path = None
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == email)) is not None:
            raise SystemExit("An account with that email already exists; nothing changed")
        account = User(email=email, password_hash=hash_password(password), role=UserRole.admin)
        db.add(account)
        db.flush()
        db.add(AuditEvent(actor_user_id=account.user_id, action="admin.provisioned", resource_type="user", resource_id=account.user_id))
        try:
            if args.generate_password:
                directory = Path(tempfile.mkdtemp(prefix="jobbridge-admin-", dir=Path.home()))
                if os.name == "nt":
                    identity = subprocess.check_output(["whoami"], text=True).strip()
                    subprocess.run(["icacls", str(directory), "/inheritance:r", "/grant:r", f"{identity}:(OI)(CI)F"], check=True, capture_output=True)
                else:
                    directory.chmod(0o700)
                credential_path = directory / "credentials.txt"
                descriptor = os.open(credential_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(descriptor, "w", encoding="utf-8") as credentials:
                    credentials.write(f"JobBridge administrator\nEmail: {email}\nPassword: {password}\nKeep private. Do not commit or share.\n")
            db.commit()
        except Exception:
            db.rollback()
            if credential_path:
                credential_path.unlink(missing_ok=True)
            raise
    print(f"Created administrator account for {email}")
    if credential_path:
        print(f"Private credentials saved to: {credential_path}")


if __name__ == "__main__":
    main()