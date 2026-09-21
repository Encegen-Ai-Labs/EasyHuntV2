from fastapi import APIRouter, Depends, UploadFile, File, Form, status, BackgroundTasks
from app.schemas.documents import BatchUploadResponse, DocumentResponse, DocumentUploadResult
from app.schemas.document_pages import DocumentPageResponse, DocumentPagesResponse, EnhancedPageImageResponse, UpdatePageTextRequest
from app.services.doc_service import DocumentService, STORAGE_BUCKET, enhanced_page_image_path
from app.services.pipeline_service import PipelineService
from app.repositories.doc_repo import DocumentRepository
from app.repositories.case_repo import CaseRepository
from app.repositories.flag_repo import FlagRepository
from app.repositories.document_page_repo import DocumentPageRepository
from app.services.translation_service import translate_pages
from app.services.embedding_service import embed_text
from app.core.logging import logger
from app.dependencies.db import get_supabase_client
from app.dependencies.auth import RoleRequirement
from app.core.exceptions import PropertySystemException, ResourceNotFoundError
from supabase import Client
from typing import Any, Dict, List

router = APIRouter(prefix="/documents", tags=["Document Infrastructure"])

MAX_BATCH_SIZE = 20

def get_doc_service(db: Client = Depends(get_supabase_client)) -> DocumentService:
    return DocumentService(DocumentRepository(db), CaseRepository(db))

def get_pipeline_service(db: Client = Depends(get_supabase_client)) -> PipelineService:
    return PipelineService(DocumentRepository(db), CaseRepository(db), FlagRepository(db), DocumentPageRepository(db))

def get_doc_page_repo(db: Client = Depends(get_supabase_client)) -> DocumentPageRepository:
    return DocumentPageRepository(db)

@router.get("", response_model=List[DocumentResponse])
def list_documents(
    case_id: str,
    current_user: Dict[str, Any] = Depends(RoleRequirement(["Reviewer", "Admin"])),
    service: DocumentService = Depends(get_doc_service),
):
    """Every document uploaded to a case, any status — used by the case workspace's
    document list. (Distinct from GET /review/{case_id}/documents, which only
    returns documents ready for the review queue.)"""
    service.authorize_case_access(case_id, current_user)
    return service.doc_repo.list_by_case(case_id)

@router.post("/upload", response_model=BatchUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_documents(
    case_id: str = Form(...),
    files: List[UploadFile] = File(...),
    background_tasks: BackgroundTasks = None,
    current_user: Dict[str, Any] = Depends(RoleRequirement(["Reviewer", "Admin"])),
    service: DocumentService = Depends(get_doc_service),
    pipeline_service: PipelineService = Depends(get_pipeline_service)
):
    if not files:
        raise PropertySystemException("At least one file is required")
    if len(files) > MAX_BATCH_SIZE:
        raise PropertySystemException(f"Cannot upload more than {MAX_BATCH_SIZE} files in a single batch")

    # Case-level authorization applies to the whole batch, not per file — a missing
    # or forbidden case fails the entire request instead of repeating the same
    # error once per file.
    service.authorize_case_access(case_id, current_user)

    results: List[DocumentUploadResult] = []
    uploaded_doc_ids: List[str] = []

    for file in files:
        try:
            file_bytes = await file.read()
            document = service.upload_file(
                case_id=case_id,
                file_name=file.filename,
                file_bytes=file_bytes,
                mime_type=file.content_type,
                current_user=current_user
            )
            results.append(DocumentUploadResult(file_name=file.filename, success=True, document=document))
            if document.get("id"):
                uploaded_doc_ids.append(document["id"])
        except PropertySystemException as e:
            # File-specific problem (bad type, oversized, etc.) — record it and
            # keep processing the rest of the batch instead of failing the request.
            results.append(DocumentUploadResult(file_name=file.filename, success=False, error=e.message))

    if uploaded_doc_ids and background_tasks is not None:
        background_tasks.add_task(pipeline_service.execute_batch, uploaded_doc_ids)

    return BatchUploadResponse(results=results)

@router.get("/{id}", response_model=DocumentResponse)
def get_document(
    id: str,
    current_user: Dict[str, Any] = Depends(RoleRequirement(["Reviewer", "Admin"])),
    service: DocumentService = Depends(get_doc_service),
):
    """Single-document status lookup — used by the frontend to poll a just-uploaded
    document's processing status (uploaded -> processing -> llm_done/flagged/...)."""
    document = service.doc_repo.get_by_id(id)
    if not document:
        raise ResourceNotFoundError("Document not found")
    service.authorize_case_access(document["case_id"], current_user)
    return document

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    id: str,
    current_user: Dict[str, Any] = Depends(RoleRequirement(["Reviewer", "Admin"])),
    service: DocumentService = Depends(get_doc_service),
):
    """Deletes a document immediately, including while it's still
    uploading/processing in the background — see
    DocumentService.delete_document for exactly what that means (soft-discard:
    the row and file are gone right away; any in-flight background pipeline
    work for it just finishes with nowhere left to write its result)."""
    service.delete_document(id, current_user)

@router.get("/{id}/pages", response_model=DocumentPagesResponse)
def get_document_pages(
    id: str,
    current_user: Dict[str, Any] = Depends(RoleRequirement(["Reviewer", "Admin"])),
    service: DocumentService = Depends(get_doc_service),
    doc_page_repo: DocumentPageRepository = Depends(get_doc_page_repo),
):
    """Full per-page text (original + English) for one document — backs the
    search UI's page viewer, since search results only carry a short snippet."""
    document = service.doc_repo.get_by_id(id)
    if not document:
        raise ResourceNotFoundError("Document not found")
    service.authorize_case_access(document["case_id"], current_user)

    pages = sorted(doc_page_repo.list_by_document(id), key=lambda p: p["page_number"])
    return DocumentPagesResponse(document_id=id, pages=pages)

@router.get("/{id}/pages/{page_number}/enhanced-image", response_model=EnhancedPageImageResponse)
def get_enhanced_page_image(
    id: str,
    page_number: int,
    current_user: Dict[str, Any] = Depends(RoleRequirement(["Admin"])),
    service: DocumentService = Depends(get_doc_service),
):
    """Admin-only: a short-lived signed URL to a page's post-OpenCV-enhanced
    image — the exact bytes OCR/Gemini both actually read (see
    pipeline_service.py's per-page loop and image_enhancement.py), not the
    raw scan/rasterization. Lets an admin see what the pipeline saw when a
    transcription looks wrong. Scoped to Admin specifically (RoleRequirement
    here, not authorize_case_access's creator-or-assigned-reviewer rule) —
    this is a pipeline-diagnostics view, not a case-review feature."""
    document = service.doc_repo.get_by_id(id)
    if not document:
        raise ResourceNotFoundError("Document not found")

    storage_path = enhanced_page_image_path(document["case_id"], id, page_number)
    try:
        signed = service.doc_repo.client.storage.from_(STORAGE_BUCKET).create_signed_url(storage_path, 300)
        url = signed.get("signedURL") if isinstance(signed, dict) else None
    except Exception:
        url = None
    if not url:
        raise ResourceNotFoundError("No enhanced image found for this page — it may not have finished processing yet")
    return EnhancedPageImageResponse(url=url)

@router.patch("/{id}/pages/{page_number}", response_model=DocumentPageResponse)
def update_document_page(
    id: str,
    page_number: int,
    payload: UpdatePageTextRequest,
    current_user: Dict[str, Any] = Depends(RoleRequirement(["Reviewer", "Admin"])),
    service: DocumentService = Depends(get_doc_service),
    doc_page_repo: DocumentPageRepository = Depends(get_doc_page_repo),
):
    """Lets a reviewer correct a page's transcribed text after the fact (a
    misread word, a garbled OCR/VLM line, etc.). Unlike editing the
    structured extracted fields (already supported, see review.py), this
    writes straight to document_pages — the same original_text/english_text
    columns search, translation, and the report builder's excerpts all read
    from — so a correction here propagates everywhere else that page's text
    is used, not just this screen.

    Editing original_text also regenerates that page's search embedding
    synchronously (one extra Gemini call per save) so semantic search
    doesn't keep ranking the page against its pre-edit text. If the
    re-embed call itself fails, the text edit is still saved — the old
    embedding is left in place (slightly stale) rather than being nulled
    out, which would silently drop the page from semantic search entirely."""
    document = service.doc_repo.get_by_id(id)
    if not document:
        raise ResourceNotFoundError("Document not found")
    service.authorize_case_access(document["case_id"], current_user)

    if payload.original_text is None and payload.english_text is None:
        raise PropertySystemException("Provide original_text and/or english_text to update")

    update_data: Dict[str, Any] = {}
    if payload.original_text is not None:
        update_data["original_text"] = payload.original_text
        embed_result = embed_text(payload.original_text)
        if embed_result["success"]:
            update_data["embedding"] = embed_result["embedding"]
        else:
            logger.error(
                "documents.page_edit_reembed_failed | document_id=%s page_number=%s error=%s",
                id, page_number, embed_result["error"],
            )
    if payload.english_text is not None:
        update_data["english_text"] = payload.english_text

    updated = doc_page_repo.update_page_text(id, page_number, update_data)
    if not updated:
        raise ResourceNotFoundError("Page not found")
    return updated

@router.post("/{id}/translate", response_model=DocumentPagesResponse)
def translate_document(
    id: str,
    current_user: Dict[str, Any] = Depends(RoleRequirement(["Reviewer", "Admin"])),
    service: DocumentService = Depends(get_doc_service),
    doc_page_repo: DocumentPageRepository = Depends(get_doc_page_repo),
):
    """Translates every page of a document to English, on demand — translation
    is no longer run automatically during upload (see pipeline_service.py),
    so the reviewer opts in per document. Runs synchronously (unlike
    /process, which backgrounds the much slower Gemini extraction) since
    Google Translate's per-page calls are fast enough that the reviewer can
    just wait for the response instead of needing to poll."""
    document = service.doc_repo.get_by_id(id)
    if not document:
        raise ResourceNotFoundError("Document not found")
    service.authorize_case_access(document["case_id"], current_user)

    pages = sorted(doc_page_repo.list_by_document(id), key=lambda p: p["page_number"])
    if not pages:
        raise PropertySystemException("This document has no pages to translate yet — it may still be processing.")

    translated = translate_pages(pages)
    doc_page_repo.update_english_text_bulk(id, [
        {"page_number": p["page_number"], "english_text": p["english_text"]} for p in translated
    ])
    return DocumentPagesResponse(document_id=id, pages=translated)

@router.post("/{id}/process")
def process_document(
    id: str,
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(RoleRequirement(["Reviewer", "Admin"])),
    pipeline_service: PipelineService = Depends(get_pipeline_service)
):
    # Enqueue execution asynchronously inside the FastAPI event loop
    background_tasks.add_task(pipeline_service.execute_analysis_pipeline, id)
    return {"message": f"Processing pipeline initiated for document {id}"}