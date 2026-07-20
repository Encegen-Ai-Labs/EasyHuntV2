from typing import Any, Dict

from fastapi import APIRouter, Depends, status
from supabase import Client

from app.dependencies.auth import RoleRequirement, get_current_user
from app.dependencies.db import get_supabase_client, get_supabase_service_client
from app.repositories.case_repo import CaseRepository
from app.repositories.report_repo import ReportRepository
from app.services.report_service import ReportGenerationService

router = APIRouter(prefix="/reports", tags=["Reports Hub"])


def get_report_repository(db: Client = Depends(get_supabase_service_client)) -> ReportRepository:
    return ReportRepository(db)

@router.post("/generate/{case_id}", status_code=status.HTTP_201_CREATED)
def generate_report(
    case_id: str,
    current_user: Dict[str, Any] = Depends(RoleRequirement(["Reviewer", "Admin"])),
    service: ReportGenerationService = Depends(get_report_service)
):
    return service.generate_pdf_report(case_id=case_id, user_id=str(current_user["id"]))

@router.get("/download/{case_id}")
def get_report_download_url(
    case_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Client = Depends(get_supabase_client)
):
    repo = ReportRepository(db)
    report = repo.get_by_case(case_id)
    if not report:
        return {"error": "Report not found"}
        
    # Generate signed, temporary download URL from private Supabase Storage bucket
    res = db.storage.from_("reports").create_signed_url(report["file_path"], expires_in=3600)
    return {"download_url": res["signedURL"]}