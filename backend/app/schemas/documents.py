from pydantic import BaseModel
from enum import Enum
from typing import List, Optional
from uuid import UUID
from datetime import datetime

class DocStatusEnum(str, Enum):
    uploaded = "uploaded"
    processing = "processing"
    ocr_done = "ocr_done"
    llm_done = "llm_done"
    under_review = "under_review"
    approved = "approved"
    flagged = "flagged"
    rejected = "rejected"
    completed = "completed"

class DocumentResponse(BaseModel):
    id: UUID
    case_id: UUID
    file_name: str
    file_path: str
    file_size: int
    mime_type: str
    status: DocStatusEnum
    created_at: datetime
    uploaded_by: Optional[UUID] = None

    class Config:
        from_attributes = True

class DocumentUploadResult(BaseModel):
    """Outcome of one file within a batch upload — files are validated and
    uploaded independently, so one bad file doesn't block the rest of the batch."""
    file_name: str
    success: bool
    document: Optional[DocumentResponse] = None
    error: Optional[str] = None

class BatchUploadResponse(BaseModel):
    results: List[DocumentUploadResult]