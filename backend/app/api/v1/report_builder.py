from fastapi import APIRouter, Depends, status
from typing import Any, Dict, List
from app.schemas.report_builder import (
    ExcerptCreate,
    ExcerptReorder,
    ExcerptResponse,
    ExcerptUpdate,
    ReportBuilderResponse,
    ReportExportResponse,
)
from app.services.report_builder_service import ReportBuilderService
from app.services.doc_service import DocumentService
from app.repositories.doc_repo import DocumentRepository
from app.repositories.case_repo import CaseRepository
from app.repositories.report_repo import ReportRepository
from app.repositories.report_excerpt_repo import ReportExcerptRepository
from app.dependencies.db import get_supabase_client
from app.dependencies.auth import RoleRequirement
from supabase import Client

router = APIRouter(prefix="/cases", tags=["Report Builder"])

def get_report_builder_service(db: Client = Depends(get_supabase_client)) -> ReportBuilderService:
    doc_repo = DocumentRepository(db)
    doc_service = DocumentService(doc_repo, CaseRepository(db))
    return ReportBuilderService(doc_service, ReportRepository(db), ReportExcerptRepository(db), doc_repo)

@router.get("/{case_id}/report-builder", response_model=ReportBuilderResponse)
def get_report_builder(
    case_id: str,
    current_user: Dict[str, Any] = Depends(RoleRequirement(["Reviewer", "Admin"])),
    service: ReportBuilderService = Depends(get_report_builder_service),
):
    """Gets (creating on first access) the case's manual, excerpt-based draft
    report — the feature that supersedes the old auto-generated LLM report flow
    (report_draft_service.py, still present, untouched, not called from here)."""
    result = service.get_report_with_excerpts(case_id, current_user)
    return ReportBuilderResponse(
        report_id=result["id"],
        case_id=result["case_id"],
        status=result["status"],
        excerpts=result["excerpts"],
    )

@router.post("/{case_id}/report-builder/excerpts", response_model=ExcerptResponse, status_code=status.HTTP_201_CREATED)
def add_excerpt(
    case_id: str,
    payload: ExcerptCreate,
    current_user: Dict[str, Any] = Depends(RoleRequirement(["Reviewer", "Admin"])),
    service: ReportBuilderService = Depends(get_report_builder_service),
):
    return service.add_excerpt(
        case_id=case_id,
        document_id=str(payload.document_id),
        page_number=payload.page_number,
        excerpt_text=payload.excerpt_text,
        note=payload.note,
        current_user=current_user,
    )

@router.patch("/{case_id}/report-builder/excerpts/{excerpt_id}", response_model=ExcerptResponse)
def update_excerpt(
    case_id: str,
    excerpt_id: str,
    payload: ExcerptUpdate,
    current_user: Dict[str, Any] = Depends(RoleRequirement(["Reviewer", "Admin"])),
    service: ReportBuilderService = Depends(get_report_builder_service),
):
    return service.update_excerpt_note(case_id, excerpt_id, payload.note, current_user, excerpt_text=payload.excerpt_text)

@router.delete("/{case_id}/report-builder/excerpts/{excerpt_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_excerpt(
    case_id: str,
    excerpt_id: str,
    current_user: Dict[str, Any] = Depends(RoleRequirement(["Reviewer", "Admin"])),
    service: ReportBuilderService = Depends(get_report_builder_service),
):
    service.remove_excerpt(case_id, excerpt_id, current_user)

@router.put("/{case_id}/report-builder/excerpts/reorder", response_model=List[ExcerptResponse])
def reorder_excerpts(
    case_id: str,
    payload: ExcerptReorder,
    current_user: Dict[str, Any] = Depends(RoleRequirement(["Reviewer", "Admin"])),
    service: ReportBuilderService = Depends(get_report_builder_service),
):
    return service.reorder_excerpts(case_id, [str(i) for i in payload.excerpt_ids], current_user)

@router.post("/{case_id}/report-builder/export", response_model=ReportExportResponse)
def export_report(
    case_id: str,
    current_user: Dict[str, Any] = Depends(RoleRequirement(["Reviewer", "Admin"])),
    service: ReportBuilderService = Depends(get_report_builder_service),
):
    """Renders the current excerpts into a PDF, uploads it, and returns a signed
    download URL — safe to call repeatedly as the report is edited, each call
    overwrites the same storage path."""
    return service.export_pdf(case_id, current_user)
