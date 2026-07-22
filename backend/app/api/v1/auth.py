from datetime import datetime, timezone
from typing import Any, Dict
from uuid import uuid4

from fastapi import APIRouter, Depends
from fastapi import status

from app.core.config import settings
from app.core.exceptions import AuthenticationError, PermissionDeniedError
from app.core.security import create_access_token, get_password_hash, verify_password
from app.dependencies.db import get_supabase_client
from app.repositories.user_repo import UserRepository
from app.schemas.auth import RoleEnum, UserLogin, UserRegister
from supabase import Client

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_user(
    payload: UserRegister,
    db: Client = Depends(get_supabase_client),
):
    repo = UserRepository(db)
    existing_user = repo.get_by_email(str(payload.email))
    if existing_user:
        raise AuthenticationError("User already exists")

    if payload.role == RoleEnum.Reviewer:
        raise PermissionDeniedError("Reviewers cannot self-register. Please contact an admin.")

    hashed_password = get_password_hash(payload.password)
    
    user_data: Dict[str, Any] = {
        "email": str(payload.email),
        "password": hashed_password,
        "role": payload.role.value,
        "organisation_name": payload.organisation_name,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    created_user = repo.create_user(user_data)
    token = create_access_token({"sub": created_user["id"], "role": created_user["role"]})

    return {
        "user_id": created_user["id"],
        "email": created_user["email"],
        "token": token,
    }


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

    token = create_access_token({"sub": user["id"], "role": user.get("role", "Vendor")})

    return {
        "access_token": token,
        "user_id": user["id"],
        "email": user.get("email"),
        "role": user.get("role", "Vendor"),
    }
