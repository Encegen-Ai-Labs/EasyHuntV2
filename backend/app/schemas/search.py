from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID

class SearchResult(BaseModel):
    document_id: UUID
    document_name: Optional[str] = None
    page_number: int
    matched_in: str  # "original" | "english" (exact mode) | "semantic" (semantic mode)
    snippet: str
    # Only set in semantic mode (0..1, higher = more relevant) — exact mode
    # has no ranking score, a substring either matched or it didn't.
    similarity: Optional[float] = None

class SearchResponse(BaseModel):
    query: str
    mode: str = "exact"
    results: List[SearchResult]
