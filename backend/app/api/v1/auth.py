
from fastapi import APIRouter, Depends

from app.core.exceptions import AuthenticationError
from app.core.rate_limiting import limit_ip
from app.core.security import create_access_token, verify_password
from app.dependencies.db import get_supabase_service_client
from app.repositories.user_repo import UserRepository
from app.schemas.auth import UserLogin
from supabase import Client

router = APIRouter(prefix="/auth", tags=["auth"])

# Self-registration has been removed. Reviewer accounts are created exclusively
# by an admin via POST /admin/reviewers (app/api/v1/admin.py). The first Admin
# is a normal users row created with scripts/create_admin.py; there is no
# env-credential login (its token had no matching users row, so every
# authenticated request failed).


# A plain `def`, so FastAPI runs it in the threadpool: password hashing is slow
# on purpose, and as an `async def` it would stall every other request.
@router.post("/login", dependencies=[Depends(limit_ip("login", "RATE_LIMIT_LOGIN"))])
def login_user(
    payload: UserLogin,
    db: Client = Depends(get_supabase_service_client),
):
    repo = UserRepository(db)

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
