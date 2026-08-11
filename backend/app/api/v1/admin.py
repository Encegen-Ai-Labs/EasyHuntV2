from datetime import datetime, timezone
from fastapi import APIRouter, Depends, status
from typing import List, Dict, Any
from app.core.exceptions import AuthenticationError
from app.core.security import get_password_hash
from app.schemas.auth import ReviewerCreate, UserResponse
from app.repositories.user_repo import UserRepository
from app.repositories.case_repo import CaseRepository
from app.repositories.doc_repo import DocumentRepository
from app.repositories.flag_repo import FlagRepository
from app.services.review_service import ReviewService
from app.dependencies.db import get_supabase_client
from app.dependencies.auth import RoleRequirement
from supabase import Client

router = APIRouter(prefix="/admin", tags=["Administration Portal"])

@router.post("/reviewers", status_code=status.HTTP_201_CREATED)
def create_reviewer(
    payload: ReviewerCreate,
    current_user: Dict[str, Any] = Depends(RoleRequirement(["Admin"])),
    db: Client = Depends(get_supabase_client)
):
    repo = UserRepository(db)
    if repo.get_by_email(str(payload.email)):
        raise AuthenticationError("User already exists")

    created_user = repo.create_user({
        "email": str(payload.email),
        "password": get_password_hash(payload.password),
        "role": "Reviewer",
        "organisation_name": payload.organisation_name,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    return {
        "user_id": created_user["id"],
        "email": created_user["email"],
        "role": created_user["role"],
        "password": payload.password,
    }

@router.get("/users", response_model=List[UserResponse])
def get_all_users(
    current_user: Dict[str, Any] = Depends(RoleRequirement(["Admin"])),
    db: Client = Depends(get_supabase_client)
):
    repo = UserRepository(db)
    return repo.list_all_users()

@router.post("/assign-reviewer")
def assign_reviewer_to_case(
    case_id: str,
    reviewer_id: str,
    current_user: Dict[str, Any] = Depends(RoleRequirement(["Admin"])),
    db: Client = Depends(get_supabase_client)
):
    service = ReviewService(
        CaseRepository(db), FlagRepository(db), DocumentRepository(db)
    )
    updated = service.assign_reviewer(case_id, reviewer_id)
    return {"message": "Reviewer successfully reassigned", "case": updated}