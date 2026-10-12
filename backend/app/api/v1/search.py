from fastapi import APIRouter, Depends, Query
from typing import Any, Dict
from app.schemas.search import TermsResponse
from app.services.search_service import SearchService
from app.services.doc_service import DocumentService
from app.repositories.doc_repo import DocumentRepository
from app.repositories.case_repo import CaseRepository
from app.repositories.document_page_repo import DocumentPageRepository
from app.dependencies.db import get_supabase_service_client
from app.dependencies.auth import RoleRequirement
from supabase import Client

router = APIRouter(prefix="/cases", tags=["Search"])

def get_search_service(db: Client = Depends(get_supabase_service_client)) -> SearchService:
    doc_repo = DocumentRepository(db)
    doc_service = DocumentService(doc_repo, CaseRepository(db))
    return SearchService(doc_service, doc_repo, DocumentPageRepository(db))

@router.get("/{case_id}/search/terms", response_model=TermsResponse)
def search_case_terms(
    case_id: str,
    q: str = Query(..., min_length=1, description="Words to look for"),
    current_user: Dict[str, Any] = Depends(RoleRequirement(["Reviewer", "Admin"])),
    service: SearchService = Depends(get_search_service)
):
    """The exact words, then close spelling variants, found in the case's
    approved documents for each word of `q`, with how often and where each
    occurs. The lawyer picks which to highlight."""
    outcome = service.find_terms_outcome(case_id, q, current_user)
    return TermsResponse(query=q, **outcome)
