from typing import Any, Dict

from fastapi import APIRouter, Depends

from app.core.config import settings
from app.core.exceptions import AuthenticationError
from app.core.security import create_access_token, verify_password
from app.dependencies.db import get_supabase_client
from app.repositories.user_repo import UserRepository
from app.schemas.auth import RoleEnum, UserLogin
from supabase import Client

router = APIRouter(prefix="/auth", tags=["auth"])

# Self-registration has been removed. Reviewer accounts are created exclusively
# by an admin via POST /admin/reviewers (app/api/v1/admin.py). Admin access is
# granted only through the ADMIN_EMAIL/ADMIN_PASSWORD environment credentials
# checked in login_user() below.


@router.post("/login")
async def login_user(
    payload: UserLogin,
    db: Client = Depends(get_supabase_client),
):
    repo = UserRepository(db)

    admin_email = getattr(settings, "ADMIN_EMAIL", None)
    admin_password = getattr(settings, "ADMIN_PASSWORD", None)
    if str(payload.email).lower() == str(admin_email).lower() and admin_password is not None:
        if payload.password == admin_password:
            token = create_access_token({"sub": "admin-seeded", "role": RoleEnum.Admin.value})
            return {
                "access_token": token,
                "user_id": "admin-seeded",
                "role": RoleEnum.Admin.value,
            }
        raise AuthenticationError("Invalid credentials")

    user = repo.get_by_email(str(payload.email))
    if not user:
        raise AuthenticationError("Invalid credentials")

    stored_hash = user.get("password")
    if not stored_hash or not verify_password(payload.password, stored_hash):
        raise AuthenticationError("Invalid credentials")

    token = create_access_token({"sub": user["id"], "role": user.get("role", "Reviewer")})

    return {
        "access_token": token,
        "user_id": user["id"],
        "email": user.get("email"),
        "role": user.get("role", "Reviewer"),
    }
