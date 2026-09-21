"""OCR data types — adapted from the same shape used by the reference
legal-scrutiny-mvp project's ocr/provider.py, kept minimal since this codebase
only ships one provider (Tesseract) rather than a pluggable set."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class BoundingBox:
    """Axis-aligned rectangle, in pixel coordinates on the rasterized page image."""
    x: int
    y: int
    w: int
    h: int

    @property
    def area(self) -> int:
        return max(0, self.w) * max(0, self.h)


@dataclass
class TextBox:
    """One detected word/text region with its recognized text + confidence.

    is_handwritten is not a real handwriting classifier — Tesseract (like most
    OCR engines trained on printed text) simply returns low confidence on
    handwritten strokes, so the router treats "OCR confidence below a
    threshold" as a proxy for "this is probably handwriting". That conflates
    genuine handwriting with blurry scans, stains, and unusual fonts — good
    enough for a routing decision, not a claim about what's actually on the
    page.
    """
    bbox: BoundingBox
    text: str
    confidence: float  # 0..1
    is_handwritten: bool = False


@dataclass
class OcrPageResult:
    """Full output of one OCR pass over a single page image."""
    boxes: List[TextBox] = field(default_factory=list)
    full_text: str = ""
    overall_confidence: float = 0.0  # area-weighted average of box confidences
    page_width: int = 0
    page_height: int = 0
    engine: str = "unknown"
    error: Optional[str] = None  # set on failure instead of raising
