from pydantic import BaseModel
from datetime import date
from uuid import UUID

class OwnershipChainRecord(BaseModel):
    sequence_order: int
    owner_name: str
    transaction_date: date
    transaction_type: str
    survey_number: str

class OwnershipChainResponse(OwnershipChainRecord):
    id: UUID
    case_id: UUID

    class Config:
        from_attributes = True