from pydantic import BaseModel
from typing import List
from uuid import UUID

class TermLocation(BaseModel):
    document_id: UUID
    page_number: int

class SearchTerm(BaseModel):
    term: str
    kind: str  # "exact" | "similar"
    count: int
    similarity: float
    locations: List[TermLocation]

class TermsResponse(BaseModel):
    query: str
    terms: List[SearchTerm]
    # Approved documents with no English text yet; English words cannot match them until translated.
    untranslated_document_ids: List[UUID] = []
