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
    document_id: Optional[UUID] = None
    flag_type: str
    severity: FlagSeverityEnum
    description: str
    status: FlagStatusEnum
    # "structural" (chain_service.py/risk_service.py) vs "llm" (the
    # extraction model reading a document's own dispute/litigation/
    # encumbrance language — see llm_extractor.py's red_flags field and
    # docs/DECISIONS.md D3). Defaults to "structural" for any pre-Phase-1
    # row the DB migration backfilled, matching the column's own DB default.
    source: str = "structural"
    resolved_by: Optional[UUID] = None
    resolution_notes: Optional[str] = None

    class Config:
        from_attributes = True