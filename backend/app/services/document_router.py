"""Per-page OCR/VLM routing.

Inspects each (already-enhanced) page image, decides whether Tesseract's
output is good enough to use directly or the page needs the VLM (Gemini),
based on how much of the page's text area looks handwritten. Adapted from
the legal-scrutiny-mvp reference project's router.py concept, rewritten
against this codebase's plain-dict/plain-function style instead of its
SQLAlchemy-oriented dataclasses.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app.core.config import settings
from app.ocr.factory import get_ocr_provider
from app.services.page_extraction_service import extract_page_text, extract_page_text_and_fields


def _analyze_page(image_bytes: bytes) -> Dict[str, Any]:
    """Runs OCR and computes the handwritten-area ratio. Returns a dict with
    the OCR result plus routing signals; never raises — OCR unavailability or
    failure just forces the VLM path."""
    ocr_provider = get_ocr_provider()

    if ocr_provider is None:
        return {"ocr_result": None, "handwritten_ratio": 1.0, "route": "vlm", "reason": "no_ocr_engine"}

    ocr_result = ocr_provider.detect_and_recognize(image_bytes)
    if ocr_result.error:
        return {"ocr_result": ocr_result, "handwritten_ratio": 1.0, "route": "vlm", "reason": f"ocr_error: {ocr_result.error}"}

    printed_area = sum(b.bbox.area for b in ocr_result.boxes if not b.is_handwritten)
    handwritten_area = sum(b.bbox.area for b in ocr_result.boxes if b.is_handwritten)
    total_area = printed_area + handwritten_area
    ratio = (handwritten_area / total_area) if total_area > 0 else 0.0

    route = "vlm" if ratio >= settings.ROUTER_HANDWRITING_THRESHOLD else "ocr"
    return {"ocr_result": ocr_result, "handwritten_ratio": ratio, "route": route, "reason": None}


def route_and_extract_page(
    image_bytes: bytes, page_number: int, also_extract_fields: bool = False,
) -> Dict[str, Any]:
    """Routes one enhanced page image through OCR or the VLM and returns:
    {page_number, original_text, source: "ocr"|"vlm", confidence, has_handwriting,
    issues: [str], structured_fields: dict | None}

    A page that goes to OCR but whose text/confidence turns out unusable
    escalates to the VLM rather than persisting a bad transcription — the
    router's job is to save VLM calls on pages that don't need them, not to
    force a page through OCR when it clearly needs the VLM.

    also_extract_fields (default False, so every existing caller is
    unaffected): if the page ends up on the VLM path, ask for structured
    fields in the same call instead of just a transcription — see
    page_extraction_service.extract_page_text_and_fields. structured_fields
    is None unless this actually happened (OCR handled the page, the VLM
    call failed, or also_extract_fields was False) — pipeline_service.py
    only sets this for single-page documents, where a document-level
    field-extraction call would otherwise immediately follow this one
    working from nothing more than what this call already transcribed.
    """
    analysis = _analyze_page(image_bytes)
    issues: List[str] = []
    ocr_result = analysis["ocr_result"]

    if analysis["route"] == "ocr" and ocr_result is not None:
        needs_fallback = (
            not ocr_result.full_text.strip()
            or ocr_result.overall_confidence < settings.OCR_FALLBACK_CONFIDENCE
        )
        handwritten_box_count = sum(1 for b in ocr_result.boxes if b.is_handwritten)

        if not needs_fallback:
            if handwritten_box_count > 0:
                issues.append(
                    f"small_handwriting_detected ({handwritten_box_count} word(s), "
                    f"ratio={analysis['handwritten_ratio']:.2f})"
                )
            return {
                "page_number": page_number,
                "original_text": ocr_result.full_text,
                "source": "ocr",
                "confidence": round(ocr_result.overall_confidence, 4),
                "has_handwriting": handwritten_box_count > 0,
                "issues": issues,
                "structured_fields": None,
            }

        issues.append(
            f"ocr_low_confidence_fallback (conf={ocr_result.overall_confidence:.2f}, "
            f"text_len={len(ocr_result.full_text)})"
        )

    # VLM path — either routed here directly (high handwriting ratio, no OCR
    # engine, OCR error) or escalated from a low-confidence OCR attempt above.
    if analysis["reason"]:
        issues.append(analysis["reason"])

    if also_extract_fields:
        vlm_result = extract_page_text_and_fields(image_bytes, mime_type="image/png")
    else:
        vlm_result = extract_page_text(image_bytes, mime_type="image/png")

    if not vlm_result["success"]:
        issues.append(f"vlm_error: {vlm_result['error']}")
        return {
            "page_number": page_number,
            "original_text": f"[page extraction failed: {vlm_result['error']}]",
            "source": "vlm",
            "confidence": 0.0,
            "has_handwriting": analysis["handwritten_ratio"] > 0,
            "issues": issues,
            "structured_fields": None,
        }

    return {
        "page_number": page_number,
        "original_text": vlm_result["text"],
        "source": "vlm",
        "confidence": None,  # the plain-text transcription prompt doesn't self-report confidence
        "has_handwriting": analysis["handwritten_ratio"] >= settings.ROUTER_HANDWRITING_THRESHOLD,
        "issues": issues,
        "structured_fields": vlm_result.get("extracted") if also_extract_fields else None,
    }
