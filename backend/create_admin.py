"""Create an administrator account for a local deployment."""
from __future__ import annotations

import argparse
from getpass import getpass

from sqlalchemy import select

from app.db.models import User, UserRole
from app.db.postgres import SessionLocal
from app.utils.security import hash_password


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("email")
    args = parser.parse_args()
    password = getpass("Administrator password (minimum 12 characters): ")
    if len(password) < 12:
        raise SystemExit("Password must contain at least 12 characters")
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == args.email.lower())) is not None:
            raise SystemExit("An account with that email already exists")
        db.add(User(email=args.email.lower(), password_hash=hash_password(password), role=UserRole.admin))
        db.commit()
    print(f"Created administrator account for {args.email.lower()}")


if __name__ == "__main__":
    main()