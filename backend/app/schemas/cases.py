from pydantic import BaseModel
from enum import Enum
from typing import Optional
from uuid import UUID
from datetime import datetime

class CaseStatusEnum(str, Enum):
    open = "open"
    processing = "processing"
    review = "review"
    completed = "completed"

class CaseCreate(BaseModel):
    property_name: str
    survey_number: str
    location: Optional[str] = None  # Accepted in POST request payload

class CaseUpdate(BaseModel):
    property_name: Optional[str] = None
    survey_number: Optional[str] = None
    location: Optional[str] = None
    status: Optional[CaseStatusEnum] = None

class CaseResponse(BaseModel):
    id: UUID
    created_by: UUID
    property_name: str
    survey_number: str
    location: Optional[str] = None
    status: CaseStatusEnum
    created_at: Optional[datetime] = None  # Now handles null/missing timestamps safely
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True