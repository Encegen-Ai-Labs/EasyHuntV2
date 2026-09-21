"""OCR provider factory — single cached instance, or None if Tesseract isn't
actually installed/reachable (the router then sends every page to the VLM,
same fallback behavior as having no OCR engine at all)."""

from __future__ import annotations

from typing import Optional

from .tesseract_provider import TesseractOcrProvider

_cached: Optional[TesseractOcrProvider] = None
_checked = False


def get_ocr_provider() -> Optional[TesseractOcrProvider]:
    global _cached, _checked
    if _checked:
        return _cached

    _checked = True
    try:
        provider = TesseractOcrProvider()
        if provider.is_available():
            _cached = provider
    except Exception:
        _cached = None

    return _cached
