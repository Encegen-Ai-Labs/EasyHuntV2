import mimetypes
from typing import Dict, Any
from app.repositories.doc_repo import DocumentRepository
from app.repositories.case_repo import CaseRepository
from app.core.exceptions import ResourceNotFoundError, PermissionDeniedError, PropertySystemException

ALLOWED_MIMETYPES = ["application/pdf", "image/png", "image/jpeg", "image/jpg"]
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

class DocumentService:
    def __init__(self, doc_repo: DocumentRepository, case_repo: CaseRepository):
        self.doc_repo = doc_repo
        self.case_repo = case_repo

    def validate_and_upload(
        self, 
        case_id: str, 
        file_name: str, 
        file_bytes: bytes, 
        mime_type: str, 
        current_user: Dict[str, Any]
    ) -> Dict[str, Any]:
        # Fetch case to check authorization rules
        case_obj = self.case_repo.get_by_id(case_id)
        if not case_obj:
            raise ResourceNotFoundError("Target case does not exist")
        
        if current_user["role"] == "Vendor" and case_obj["vendor_id"] != current_user["id"]:
            raise PermissionDeniedError("Cannot upload documents to cases you do not own")

        # Validate file properties
        file_size = len(file_bytes)
        if file_size > MAX_FILE_SIZE:
            raise PropertySystemException("File exceeds maximum allowed size of 10MB")
        if mime_type not in ALLOWED_MIMETYPES:
            raise PropertySystemException(f"Unsupported media type. Allowed: {ALLOWED_MIMETYPES}")

        # Supabase Storage path layout: cases/{case_id}/{filename}
        storage_path = f"cases/{case_id}/{file_name}"
        
        # Uploading payload directly via base supabase client storage interface
        storage_response = self.doc_repo.client.storage.from_("documents").upload(
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
            "status": "uploaded"
        }
        return self.doc_repo.create_document(doc_payload)