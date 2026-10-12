"""Create the first Admin user in the users table.

Usage (from the api container, in /app):
    python -m scripts.create_admin

Reads ADMIN_EMAIL and ADMIN_PASSWORD from the environment; if ADMIN_PASSWORD
is unset it prompts for one with getpass. Refuses to run if the email already
exists. Never prints the password.
"""
import getpass
import os
import sys
from datetime import datetime, timezone

MIN_PASSWORD_LENGTH = 8  # matches ReviewerCreate.password


def create_admin(repo, email: str, password: str, hash_password, organisation_name: str = "Admin") -> dict:
    email = email.strip()
    if not email:
        raise ValueError("ADMIN_EMAIL is required")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
    if repo.get_by_email(email):
        raise ValueError(f"A user with email {email} already exists; nothing was changed")
    return repo.create_user({
        "email": email,
        "password": hash_password(password),
        "role": "Admin",
        "organisation_name": organisation_name,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })


def main() -> int:
    from app.core.security import get_password_hash
    from app.dependencies.db import get_supabase_service_client
    from app.repositories.user_repo import UserRepository

    email = os.environ.get("ADMIN_EMAIL", "")
    password = os.environ.get("ADMIN_PASSWORD") or getpass.getpass("Admin password: ")
    try:
        user = create_admin(UserRepository(get_supabase_service_client()), email, password, get_password_hash)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Created Admin user {user['email']} (id {user['id']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
