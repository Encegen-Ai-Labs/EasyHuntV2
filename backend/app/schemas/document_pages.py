from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID

class DocumentPageResponse(BaseModel):
    page_number: int
    original_text: Optional[str] = None
    english_text: Optional[str] = None

class DocumentPagesResponse(BaseModel):
    document_id: UUID
    pages: List[DocumentPageResponse]

class UpdatePageTextRequest(BaseModel):
    """At least one of these must be set — enforced in the route, not here,
    since "both absent" is a request-shape error the caller should see as a
    clear message rather than a generic 422."""
    original_text: Optional[str] = None
    english_text: Optional[str] = None

class EnhancedPageImageResponse(BaseModel):
    """A time-limited signed URL to a page's post-OpenCV-enhanced image —
    see app/services/image_enhancement.py and the Admin-only
    GET /documents/{id}/pages/{page_number}/enhanced-image route."""
    url: str
