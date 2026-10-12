from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from supabase import Client

from app.dependencies.auth import RoleRequirement
from app.dependencies.db import get_supabase_service_client
from app.repositories.base import BaseRepository
from app.repositories.case_repo import CaseRepository
from app.repositories.doc_repo import DocumentRepository
from app.repositories.flag_repo import FlagRepository
from app.repositories.report_excerpt_repo import ReportExcerptRepository
from app.repositories.report_repo import ReportRepository
from app.schemas.report_generation import DraftRequest, ExportRequest, ReportDraft, ReportFormat
from app.services import report_formats
from app.services.doc_service import DocumentService
from app.services.report_builder_service import ReportBuilderService
from app.services.report_generation_service import ReportGenerationService

router = APIRouter(prefix="/cases", tags=["Report Generation"])

_ROLES = ["Reviewer", "Admin"]


def get_report_generation_service(db: Client = Depends(get_supabase_service_client)) -> ReportGenerationService:
    doc_repo = DocumentRepository(db)
    doc_service = DocumentService(doc_repo, CaseRepository(db))
    builder = ReportBuilderService(doc_service, ReportRepository(db), ReportExcerptRepository(db), doc_repo)
    return ReportGenerationService(doc_service, doc_repo, BaseRepository(db), FlagRepository(db), builder)


@router.get("/{case_id}/report/formats", response_model=List[ReportFormat])
def list_report_formats(
    case_id: str,
    current_user: Dict[str, Any] = Depends(RoleRequirement(_ROLES)),
):
    """The title search report plus one entry per bank template."""
    return report_formats.list_formats()


@router.post("/{case_id}/report/draft", response_model=ReportDraft)
def create_report_draft(
    case_id: str,
    payload: DraftRequest,
    current_user: Dict[str, Any] = Depends(RoleRequirement(_ROLES)),
    service: ReportGenerationService = Depends(get_report_generation_service),
):
    """Builds an editable draft from the case's approved documents. Needs at
    least one approved document."""
    return service.build_draft(case_id, payload.format_id, current_user)


@router.post("/{case_id}/report/export")
def export_report(
    case_id: str,
    payload: ExportRequest,
    current_user: Dict[str, Any] = Depends(RoleRequirement(_ROLES)),
    service: ReportGenerationService = Depends(get_report_generation_service),
):
    """Writes the draft as the lawyer edited it to a Word or PDF file and
    streams it back; nothing is stored."""
    result = service.export(case_id, payload.draft, payload.file_type, current_user)
    return Response(
        content=result["content"],
        media_type=result["media_type"],
        headers={
            "Content-Disposition": f'attachment; filename="{result["filename"]}"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
