from fastapi import APIRouter, Depends, status
from typing import List, Dict, Any, Optional
from uuid import UUID

from app.schemas.flags import FlagCreate, FlagResponse, FlagResolve, FlagStatusEnum
from app.repositories.flag_repo import FlagRepository, FLAGS_TABLE
from app.services.review_service import ReviewService
from app.repositories.case_repo import CaseRepository
from app.dependencies.db import get_supabase_client, get_supabase_service_client
from app.dependencies.auth import get_current_user, RoleRequirement
from app.core.exceptions import ResourceNotFoundError
from supabase import Client

router = APIRouter(prefix="/flags", tags=["Flags Auditing & Automation"])


def get_flag_repository(db: Client = Depends(get_supabase_service_client)) -> FlagRepository:
    return FlagRepository(db)


def get_review_service(db: Client = Depends(get_supabase_service_client)) -> ReviewService:
    return ReviewService(CaseRepository(db), FlagRepository(db))

@router.get("", response_model=List[FlagResponse])
def list_flags(
    case_id: Optional[UUID] = None,
    status: Optional[FlagStatusEnum] = None,
    current_user: Dict[str, Any] = Depends(get_current_user),
    flag_repo: FlagRepository = Depends(get_flag_repository)
):
    """
    Retrieve system and reviewer flags.
    - **Admin/Reviewer**: Can view all flags or filter dynamically.
    """
    query_filters: Dict[str, Any] = {}
    if case_id:
        query_filters["case_id"] = str(case_id)
    if status:
        query_filters["status"] = status.value

    return flag_repo.select(FLAGS_TABLE, query_filters)

@router.post("/{case_id}", response_model=FlagResponse, status_code=status.HTTP_201_CREATED)
def raise_manual_flag(
    case_id: UUID,
    payload: FlagCreate,
    current_user: Dict[str, Any] = Depends(RoleRequirement(["Reviewer", "Admin"])),
    flag_repo: FlagRepository = Depends(get_flag_repository)
):
    """
    Manually raise an extraction discrepancy flag against a case file.
    Restricted to **Reviewers** and **Admins**.
    """
    case_repo = CaseRepository(flag_repo.client)
    case_obj = case_repo.get_by_id(str(case_id))
    if not case_obj:
        raise ResourceNotFoundError("Target legal case record could not be found.")

    flag_payload = {
        "case_id": str(case_id),
        "flag_type": payload.flag_type,
        "severity": payload.severity.value,
        "description": payload.description,
        "status": FlagStatusEnum.raised.value
    }
    return flag_repo.create_flag(flag_payload)

@router.put("/{flag_id}/resolve", response_model=FlagResponse)
def resolve_flag(
    flag_id: UUID,
    payload: FlagResolve,
    current_user: Dict[str, Any] = Depends(RoleRequirement(["Reviewer", "Admin"])),
    review_service: ReviewService = Depends(get_review_service)
):
    """
    Update flag resolution logs and modify status back to structured clear metrics.
    Restricted to **Reviewers** and **Admins**.
    """
    flag_obj = review_service.flag_repo.select_one(FLAGS_TABLE, {"id": str(flag_id)})
    if not flag_obj:
        raise ResourceNotFoundError("Discrepancy flag identifier not found in cluster.")

    return review_service.resolve_flag(
        flag_id=str(flag_id),
        user_id=str(current_user["id"]),
        resolution_notes=payload.resolution_notes,
        status=payload.status.value
    )