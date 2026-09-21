from fastapi import APIRouter, Depends, Query
from typing import Any, Dict
from app.schemas.search import SearchResponse
from app.services.search_service import SearchService
from app.services.doc_service import DocumentService
from app.repositories.doc_repo import DocumentRepository
from app.repositories.case_repo import CaseRepository
from app.repositories.document_page_repo import DocumentPageRepository
from app.dependencies.db import get_supabase_client
from app.dependencies.auth import RoleRequirement
from supabase import Client

router = APIRouter(prefix="/cases", tags=["Search"])

def get_search_service(db: Client = Depends(get_supabase_client)) -> SearchService:
    doc_repo = DocumentRepository(db)
    doc_service = DocumentService(doc_repo, CaseRepository(db))
    return SearchService(doc_service, doc_repo, DocumentPageRepository(db))

@router.get("/{case_id}/search", response_model=SearchResponse)
def search_case_documents(
    case_id: str,
    q: str = Query(..., min_length=1, description="Search text"),
    mode: str = Query(
        "exact",
        pattern="^(exact|semantic)$",
        description='"exact" for literal substring matching, "semantic" for meaning-based matching via embeddings',
    ),
    current_user: Dict[str, Any] = Depends(RoleRequirement(["Reviewer", "Admin"])),
    service: SearchService = Depends(get_search_service)
):
    """Search across every document in a case, page-attributed.

    exact mode: case-insensitive literal substring match across both
    original-language and English text.

    semantic mode: embedding-based similarity search (see embedding_service.py
    and migrations/0005_document_pages_embedding.sql) — finds conceptually
    related text even with no shared substring. Falls back to exact mode if
    embedding the query itself fails."""
    results = service.search_case(case_id, q, current_user, mode=mode)
    return SearchResponse(query=q, mode=mode, results=results)
