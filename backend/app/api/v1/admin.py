from fastapi import APIRouter, Depends, status
from typing import List, Dict, Any
from app.schemas.auth import UserResponse
from app.repositories.user_repo import UserRepository
from app.repositories.case_repo import CaseRepository
from app.dependencies.db import get_supabase_client
from app.dependencies.auth import RoleRequirement
from supabase import Client

router = APIRouter(prefix="/admin", tags=["Administration Portal"])

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
    repo = CaseRepository(db)
    updated = repo.update_case(case_id, {"reviewer_id": reviewer_id})
    return {"message": "Reviewer successfully reassigned", "case": updated}