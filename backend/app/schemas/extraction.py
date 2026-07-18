from pydantic import BaseModel, ConfigDict, Field
from enum import Enum
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime

class ExtractionConfidenceEnum(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"

class ExtractionStatusEnum(str, Enum):
    pending_review = "pending_review"
    approved = "approved"
    rejected = "rejected"

class ExtractionBase(BaseModel):
    document_id: UUID
    llm_raw_output: Dict[str, Any] = Field(default_factory=dict, description="Raw JSON dictionary returned by the LLM")
    validated_output: Dict[str, Any] = Field(default_factory=dict, description="JSON dictionary after systematic validation checks")
    human_correction: Optional[Dict[str, Any]] = Field(None, description="Modifications performed by the manual reviewer")
    model_used: str = Field(..., examples=["claude-haiku", "glm-4.5v"])
    confidence: ExtractionConfidenceEnum
    validation_errors: Optional[List[Dict[str, Any]]] = Field(None, description="List of failed system validation checks")
    status: ExtractionStatusEnum = ExtractionStatusEnum.pending_review

class ExtractionCreate(ExtractionBase):
    pass

class ExtractionUpdate(BaseModel):
    validated_output: Optional[Dict[str, Any]] = None
    human_correction: Optional[Dict[str, Any]] = None
    confidence: Optional[ExtractionConfidenceEnum] = None
    validation_errors: Optional[List[Dict[str, Any]]] = None
    status: Optional[ExtractionStatusEnum] = None
    reviewed_by: Optional[UUID] = None
    reviewed_at: Optional[datetime] = None

class ExtractionResponse(ExtractionBase):
    id: UUID
    reviewed_by: Optional[UUID] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)