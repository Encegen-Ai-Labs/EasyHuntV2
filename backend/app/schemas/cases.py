from pydantic import BaseModel
from enum import Enum
from typing import Optional, List
from uuid import UUID
from datetime import datetime

class CaseStatusEnum(str, Enum):
    open = "open"
    processing = "processing"
    review = "review"
    completed = "completed"

class CaseCreate(BaseModel):
    property_address: str
    survey_number: str

class CaseUpdate(BaseModel):
    property_address: Optional[str] = None
    survey_number: Optional[str] = None
    status: Optional[CaseStatusEnum] = None
    reviewer_id: Optional[UUID] = None

class CaseResponse(BaseModel):
    id: UUID
    vendor_id: UUID
    reviewer_id: Optional[UUID] = None
    property_address: str
    survey_number: str
    status: CaseStatusEnum
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True