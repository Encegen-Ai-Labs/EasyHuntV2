from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query, status
from typing import List, Dict, Any
from app.core.exceptions import AuthenticationError, PropertySystemException
from app.core.logging import logger
from app.core.redaction import safe_error
from app.services import llm_usage
from app.core.security import get_password_hash
from app.schemas.auth import ReviewerCreate, UserResponse
from app.repositories.user_repo import UserRepository
from app.repositories.case_repo import CaseRepository
from app.repositories.doc_repo import DocumentRepository
from app.repositories.flag_repo import FlagRepository
from app.services.review_service import ReviewService
from app.dependencies.db import get_supabase_service_client
from app.dependencies.auth import RoleRequirement
from supabase import Client

router = APIRouter(prefix="/admin", tags=["Administration Portal"])

@router.post("/reviewers", status_code=status.HTTP_201_CREATED)
def create_reviewer(
    payload: ReviewerCreate,
    current_user: Dict[str, Any] = Depends(RoleRequirement(["Admin"])),
    db: Client = Depends(get_supabase_service_client)
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

@router.get("/usage")
def get_usage(
    days: int = Query(7, ge=1, le=90),
    current_user: Dict[str, Any] = Depends(RoleRequirement(["Admin"])),
):
    """What the paid models were used for over the last `days` days: calls,
    tokens, estimated cost, failures. Admin only. Costs are estimates from
    the prices in settings, not a bill."""
    try:
        return llm_usage.load_summary(days)
    except Exception as exc:
        logger.error("admin.usage_unavailable | reason=%s", safe_error(exc, 200))
        raise PropertySystemException(
            "Usage data is not available yet. Apply migrations/0010_llm_usage.sql to the database.",
            status_code=503,
        )

@router.get("/errors")
def get_recent_errors(
    limit: int = Query(50, ge=1, le=200),
    current_user: Dict[str, Any] = Depends(RoleRequirement(["Admin"])),
    db: Client = Depends(get_supabase_service_client),
):
    """The most recent server errors (secrets removed): when, what, and which
    user, case and document it was for. Admin only."""
    try:
        rows = (
            db.table("app_errors")
            .select("created_at,event,message,exception,request_id,user_id,case_id,document_id")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
            .data
        )
    except Exception as exc:
        logger.warning("admin.errors_unavailable | reason=%s", safe_error(exc, 200))
        raise PropertySystemException(
            "The error list is not available yet. Apply migrations/0011_app_errors.sql to the database.",
            status_code=503,
        )
    return {"errors": rows}

@router.get("/users", response_model=List[UserResponse])
def get_all_users(
    current_user: Dict[str, Any] = Depends(RoleRequirement(["Admin"])),
    db: Client = Depends(get_supabase_service_client)
):
    repo = UserRepository(db)
    return repo.list_all_users()

@router.post("/assign-reviewer")
def assign_reviewer_to_case(
    case_id: str,
    reviewer_id: str,
    current_user: Dict[str, Any] = Depends(RoleRequirement(["Admin"])),
    db: Client = Depends(get_supabase_service_client)
):
    service = ReviewService(
        CaseRepository(db), FlagRepository(db), DocumentRepository(db)
    )
    updated = service.assign_reviewer(case_id, reviewer_id)
    return {"message": "Reviewer successfully reassigned", "case": updated}