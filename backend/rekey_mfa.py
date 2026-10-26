"""Re-encrypt stored authenticator secrets with this host's MFA_ENCRYPTION_KEY.

Run after restoring a database from another host (e.g. a development laptop) whose secrets were
encrypted with a different key. Secrets that already decrypt with the current key are left alone.
Without --old-key, the development key derived from the default JWT_SECRET is tried.
"""
from __future__ import annotations

import argparse
import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select

from app.config import Settings
from app.db.models import AuditEvent, User
from app.db.postgres import SessionLocal
from app.utils.mfa import decrypt_secret, encrypt_secret


def development_key(jwt_secret: str) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(b"jobbridge-mfa:" + jwt_secret.encode()).digest()).decode()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--old-key", action="append", default=[], help="Fernet key used by the source host (repeatable)")
    args = parser.parse_args()
    old_keys = [Fernet(key) for key in args.old_key] or [Fernet(development_key(Settings.model_fields["jwt_secret"].default))]
    current = rekeyed = unreadable = 0
    with SessionLocal() as db:
        for user in db.scalars(select(User).where(User.mfa_secret_encrypted.is_not(None)).with_for_update()):
            try:
                decrypt_secret(user.mfa_secret_encrypted)
                current += 1
                continue
            except ValueError:
                pass
            for key in old_keys:
                try:
                    secret = key.decrypt(user.mfa_secret_encrypted.encode()).decode()
                except InvalidToken:
                    continue
                user.mfa_secret_encrypted = encrypt_secret(secret)
                db.add(AuditEvent(actor_user_id=user.user_id, action="mfa.rekeyed", resource_type="user", resource_id=user.user_id))
                rekeyed += 1
                break
            else:
                unreadable += 1
                print(f"Cannot decrypt the secret for {user.email}; reset it with reset_mfa.py")
        db.commit()
    print(f"Authenticator secrets: {rekeyed} re-encrypted, {current} already current, {unreadable} unreadable")


if __name__ == "__main__":
    main()
