from pydantic import BaseModel
from enum import Enum
from typing import Optional
from uuid import UUID

class FlagSeverityEnum(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"

class FlagStatusEnum(str, Enum):
    raised = "raised"
    resolved = "resolved"
    ignored = "ignored"

class FlagCreate(BaseModel):
    flag_type: str
    severity: FlagSeverityEnum
    description: str

class FlagResolve(BaseModel):
    resolution_notes: str
    status: FlagStatusEnum = FlagStatusEnum.resolved

class FlagResponse(BaseModel):
    id: UUID
    case_id: UUID
    flag_type: str
    severity: FlagSeverityEnum
    description: str
    status: FlagStatusEnum
    resolved_by: Optional[UUID] = None
    resolution_notes: Optional[str] = None

    class Config:
        from_attributes = True