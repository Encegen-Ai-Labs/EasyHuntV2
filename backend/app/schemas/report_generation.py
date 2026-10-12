from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

# Limits keep one request from carrying an absurdly large document.
MAX_BLOCKS = 400
MAX_ROWS = 500


class ReportFormat(BaseModel):
    id: str
    kind: Literal["title_search", "bank"]
    label: str


class DraftBlock(BaseModel):
    type: Literal["paragraph", "table"]
    text: str = ""
    columns: List[str] = Field(default_factory=list)
    rows: List[List[str]] = Field(default_factory=list, max_length=MAX_ROWS)


class DraftSection(BaseModel):
    id: str
    heading: str
    blocks: List[DraftBlock] = Field(default_factory=list, max_length=MAX_BLOCKS)


class DraftField(BaseModel):
    name: str
    label: str
    type: str = "text"
    options: List[str] = Field(default_factory=list)
    source: str = ""
    review_level: str = ""
    required: bool = False
    value: str = ""
    group: str = ""
    # True when the value was filled from the approved documents (so the screen can ask the lawyer to check it).
    suggested: bool = False


class DraftLoop(BaseModel):
    name: str
    label: str
    item_fields: List[str] = Field(default_factory=list)
    # nested list name -> what it holds ("string"); edited one entry per line
    nested_lists: Dict[str, str] = Field(default_factory=dict)
    rows: List[Dict[str, Any]] = Field(default_factory=list, max_length=MAX_ROWS)
    suggested: bool = False


class ReportDraft(BaseModel):
    format_id: str
    kind: Literal["title_search", "bank"]
    title: str
    bank: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
    sections: List[DraftSection] = Field(default_factory=list)
    fields: List[DraftField] = Field(default_factory=list)
    loops: List[DraftLoop] = Field(default_factory=list)


class DraftRequest(BaseModel):
    format_id: str


class ExportRequest(BaseModel):
    draft: ReportDraft
    file_type: Literal["docx", "pdf"]
