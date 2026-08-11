from fastapi import APIRouter, Depends
from typing import Dict, Any, List
from app.schemas.flags import FlagResolve, FlagResponse
from app.schemas.extraction import ReviewSubmission
from app.schemas.cases import CaseResponse
from app.services.review_service import ReviewService
from app.repositories.case_repo import CaseRepository
from app.repositories.flag_repo import FlagRepository
from app.repositories.doc_repo import DocumentRepository
from app.dependencies.db import get_supabase_client
from app.dependencies.auth import RoleRequirement
from supabase import Client

router = APIRouter(prefix="/review", tags=["Review System"])

def get_review_service(db: Client = Depends(get_supabase_client)) -> ReviewService:
    return ReviewService(CaseRepository(db), FlagRepository(db), DocumentRepository(db))

@router.get("/pending", response_model=List[CaseResponse])
def get_pending_reviews(
    current_user: Dict[str, Any] = Depends(RoleRequirement(["Reviewer", "Admin"])),
    db: Client = Depends(get_supabase_client)
):
    repo = CaseRepository(db)
    if current_user.get("role") == "Reviewer":
        return [
            case for case in repo.list_by_reviewer(str(current_user["id"]))
            if case.get("status") == "review"
        ]
    return repo.select("cases", {"status": "review"})

@router.get("/{case_id}/documents")
def get_case_documents_for_review(
    case_id: str,
    current_user: Dict[str, Any] = Depends(RoleRequirement(["Reviewer", "Admin"])),
    service: ReviewService = Depends(get_review_service)
):
    return service.get_case_documents_for_review(case_id)

@router.patch("/documents/{document_id}")
def submit_document_review(
    document_id: str,
    payload: ReviewSubmission,
    current_user: Dict[str, Any] = Depends(RoleRequirement(["Reviewer", "Admin"])),
    service: ReviewService = Depends(get_review_service)
):
    return service.submit_document_review(
        document_id=document_id,
        reviewer_id=str(current_user["id"]),
        validated_output=payload.validated_output,
        review_notes=payload.review_notes,
        decision=payload.decision.value,
    )

@router.post("/flag/{flag_id}/resolve", response_model=FlagResponse)
def resolve_system_flag(
    flag_id: str,
    payload: FlagResolve,
    current_user: Dict[str, Any] = Depends(RoleRequirement(["Reviewer", "Admin"])),
    service: ReviewService = Depends(get_review_service)
):
    return service.resolve_flag(
        flag_id=flag_id,
        user_id=str(current_user["id"]),
        resolution_notes=payload.resolution_notes,
        status=payload.status.value
    )

@router.post("/{case_id}/decision")
def finalize_case_review(
    case_id: str,
    decision: str, # "approve" or "reject"
    current_user: Dict[str, Any] = Depends(RoleRequirement(["Reviewer", "Admin"])),
    service: ReviewService = Depends(get_review_service)
):
    return service.finalize_review(case_id, decision)