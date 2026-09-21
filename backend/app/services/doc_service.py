import mimetypes
from typing import Dict, Any
from app.repositories.doc_repo import DocumentRepository
from app.repositories.case_repo import CaseRepository
from app.repositories.base import BaseRepository
from app.core.exceptions import ResourceNotFoundError, PermissionDeniedError, PropertySystemException
from app.core.logging import logger
from datetime import datetime, timezone
ALLOWED_MIMETYPES = ["application/pdf", "image/png", "image/jpeg", "image/jpg"]
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
STORAGE_BUCKET = "documents"


def enhanced_page_image_path(case_id: str, document_id: str, page_number: int) -> str:
    """Storage path for a page's post-OpenCV-enhancement image (see
    image_enhancement.py) — the same bucket as the original uploaded file,
    under a distinct "enhanced/" prefix so the two never collide. Computed
    from ids alone (no DB row needed to look it up) since document_id +
    page_number is already unique per page."""
    return f"cases/{case_id}/enhanced/{document_id}/page_{page_number}.png"

class DocumentService:
    def __init__(self, doc_repo: DocumentRepository, case_repo: CaseRepository):
        self.doc_repo = doc_repo
        self.case_repo = case_repo

    def authorize_case_access(self, case_id: str, current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Case-level authorization, shared by every file in a batch upload so it's
        checked once per request instead of once per file."""
        case_obj = self.case_repo.get_by_id(case_id)
        if not case_obj:
            raise ResourceNotFoundError("Target case does not exist")

        if current_user["role"] == "Reviewer":
            owns_case = (
                case_obj.get("created_by") == current_user["id"]
                or case_obj.get("reviewer_id") == current_user["id"]
            )
            if not owns_case:
                raise PermissionDeniedError("You can only upload documents to cases you created or have been assigned to review")
        return case_obj

    def upload_file(
        self,
        case_id: str,
        file_name: str,
        file_bytes: bytes,
        mime_type: str,
        current_user: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validates and stores a single file. Assumes case-level authorization has
        already been checked via authorize_case_access()."""
        file_size = len(file_bytes)
        if file_size > MAX_FILE_SIZE:
            raise PropertySystemException("File exceeds maximum allowed size of 10MB")
        if mime_type not in ALLOWED_MIMETYPES:
            raise PropertySystemException(f"Unsupported media type. Allowed: {ALLOWED_MIMETYPES}")

        # Supabase Storage path layout: cases/{case_id}/{filename}
        storage_path = f"cases/{case_id}/{file_name}"

        # Uploading payload directly via base supabase client storage interface
        self.doc_repo.client.storage.from_(STORAGE_BUCKET).upload(
            path=storage_path,
            file=file_bytes,
            file_options={"content-type": mime_type, "x-upsert": "true"}
        )

        doc_payload = {
            "case_id": case_id,
            "file_name": file_name,
            "file_path": storage_path,
            "file_size": file_size,
            "mime_type": mime_type,
            "status": "processing",
            "uploaded_by": current_user["id"],
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        return self.doc_repo.create_document(doc_payload)

    def validate_and_upload(
        self,
        case_id: str,
        file_name: str,
        file_bytes: bytes,
        mime_type: str,
        current_user: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Single-file convenience wrapper: authorize_case_access() + upload_file().
        Kept for callers that only ever upload one file at a time."""
        self.authorize_case_access(case_id, current_user)
        return self.upload_file(case_id, file_name, file_bytes, mime_type, current_user)

    def delete_document(self, doc_id: str, current_user: Dict[str, Any]) -> None:
        """Deletes an uploaded document immediately — storage file + DB row —
        including while it's still uploading/processing in the background.

        This is a soft-discard, not true cancellation: there's no
        cancellation hook into pipeline_service.py's background thread, so
        in-flight OCR/VLM work for this document (if any) just keeps running
        to completion rather than being interrupted mid-call. What this
        function guarantees instead is that there's nothing left for that
        work to land in by the time it finishes — child rows are removed
        first, so the pipeline's own extraction insert (pipeline_service.py)
        either never happens (document already gone) or fails safely on a
        now-nonexistent document_id, which it already handles without
        crashing the batch (see pipeline_service.execute_batch's crash
        handling).
        """
        document = self.doc_repo.get_by_id(doc_id)
        if not document:
            raise ResourceNotFoundError("Document not found")
        self.authorize_case_access(document["case_id"], current_user)

        generic_repo = BaseRepository(self.doc_repo.client)

        # Child rows first. document_pages cascades on its own FK (see
        # migrations/0001_document_pages.sql), but extractions' delete
        # behavior isn't recorded anywhere in this repo — the live schema
        # lives in the Supabase dashboard, not version control (see that
        # migration's own comment) — so delete it explicitly rather than
        # assume a cascade is set up for it too.
        try:
            generic_repo.delete("extractions", {"document_id": doc_id})
        except Exception as e:
            logger.error("doc_service.extractions_delete_failed | document_id=%s error=%s", doc_id, e)

        try:
            self.doc_repo.client.storage.from_(STORAGE_BUCKET).remove([document["file_path"]])
        except Exception as e:
            logger.error("doc_service.storage_delete_failed | document_id=%s error=%s", doc_id, e)

        generic_repo.delete("documents", {"id": doc_id})
        logger.info("doc_service.document_deleted | document_id=%s case_id=%s", doc_id, document["case_id"])
