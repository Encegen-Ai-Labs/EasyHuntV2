from pydantic import BaseModel
from enum import Enum
from typing import Optional
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