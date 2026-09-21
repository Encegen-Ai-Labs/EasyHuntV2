from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID
from datetime import datetime

class ExcerptCreate(BaseModel):
    document_id: UUID
    page_number: int
    excerpt_text: str = Field(..., min_length=1)
    note: Optional[str] = None

class ExcerptUpdate(BaseModel):
    note: Optional[str] = None
    excerpt_text: Optional[str] = Field(default=None, min_length=1)

class ExcerptReorder(BaseModel):
    excerpt_ids: List[UUID] = Field(..., description="Excerpt ids in the desired display order")

class ExcerptResponse(BaseModel):
    id: UUID
    document_id: UUID
    document_name: Optional[str] = None
    page_number: int
    excerpt_text: str
    sequence_order: int
    note: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class ReportBuilderResponse(BaseModel):
    report_id: UUID
    case_id: UUID
    status: str
    excerpts: List[ExcerptResponse]

class ReportExportResponse(BaseModel):
    file_path: str
    download_url: str
