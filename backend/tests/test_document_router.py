"""Tests for app/services/document_router.py — the OCR-vs-VLM routing
decision. OCR and VLM calls are both mocked; this only tests the routing
logic itself (ratio computation, fallback triggers), not real Tesseract/Gemini
output."""

from app.ocr.provider import BoundingBox, OcrPageResult, TextBox
from app.services import document_router


class FakeOcrProvider:
    def __init__(self, result: OcrPageResult):
        self._result = result

    def detect_and_recognize(self, image_bytes):
        return self._result


def _printed_box(text="word", conf=0.95):
    return TextBox(bbox=BoundingBox(x=0, y=0, w=100, h=20), text=text, confidence=conf, is_handwritten=False)


def _handwritten_box(text="sig", conf=0.3):
    return TextBox(bbox=BoundingBox(x=0, y=0, w=100, h=20), text=text, confidence=conf, is_handwritten=True)


def test_mostly_printed_page_routes_to_ocr(monkeypatch):
    ocr_result = OcrPageResult(
        boxes=[_printed_box() for _ in range(10)],
        full_text="ten printed words",
        overall_confidence=0.9,
        engine="tesseract",
    )
    monkeypatch.setattr(document_router, "get_ocr_provider", lambda: FakeOcrProvider(ocr_result))
    monkeypatch.setattr(document_router, "extract_page_text", lambda img, mime_type="image/png": (_ for _ in ()).throw(AssertionError("VLM should not be called")))

    result = document_router.route_and_extract_page(b"page-bytes", page_number=1)

    assert result["source"] == "ocr"
    assert result["original_text"] == "ten printed words"
    assert result["has_handwriting"] is False
    assert result["issues"] == []


def test_heavily_handwritten_page_routes_to_vlm(monkeypatch):
    ocr_result = OcrPageResult(
        boxes=[_handwritten_box() for _ in range(10)],
        full_text="garbled ocr attempt",
        overall_confidence=0.3,
        engine="tesseract",
    )
    monkeypatch.setattr(document_router, "get_ocr_provider", lambda: FakeOcrProvider(ocr_result))
    monkeypatch.setattr(
        document_router, "extract_page_text",
        lambda img, mime_type="image/png": {"success": True, "text": "vlm transcription", "error": None},
    )

    result = document_router.route_and_extract_page(b"page-bytes", page_number=1)

    assert result["source"] == "vlm"
    assert result["original_text"] == "vlm transcription"
    assert result["has_handwriting"] is True


def test_small_handwriting_stays_on_ocr_but_gets_flagged(monkeypatch):
    # Point 3 from the feature request: a page that's mostly printed with just
    # a signature/date handwritten should still go through OCR (fast path),
    # but carry a flag so the reviewer knows there's handwriting present.
    boxes = [_printed_box() for _ in range(19)] + [_handwritten_box()]
    ocr_result = OcrPageResult(boxes=boxes, full_text="mostly printed text", overall_confidence=0.92, engine="tesseract")
    monkeypatch.setattr(document_router, "get_ocr_provider", lambda: FakeOcrProvider(ocr_result))
    monkeypatch.setattr(document_router, "extract_page_text", lambda img, mime_type="image/png": (_ for _ in ()).throw(AssertionError("VLM should not be called")))

    result = document_router.route_and_extract_page(b"page-bytes", page_number=1)

    assert result["source"] == "ocr"
    assert result["has_handwriting"] is True
    assert any("small_handwriting_detected" in issue for issue in result["issues"])


def test_low_confidence_ocr_falls_back_to_vlm(monkeypatch):
    # Ratio is low (mostly-printed by box count) but OCR's own confidence on
    # those boxes is too low to trust — escalate rather than persist bad text.
    ocr_result = OcrPageResult(
        boxes=[_printed_box(conf=0.4) for _ in range(10)],
        full_text="low confidence garbage",
        overall_confidence=0.4,
        engine="tesseract",
    )
    monkeypatch.setattr(document_router, "get_ocr_provider", lambda: FakeOcrProvider(ocr_result))
    monkeypatch.setattr(
        document_router, "extract_page_text",
        lambda img, mime_type="image/png": {"success": True, "text": "vlm rescued this page", "error": None},
    )

    result = document_router.route_and_extract_page(b"page-bytes", page_number=1)

    assert result["source"] == "vlm"
    assert result["original_text"] == "vlm rescued this page"
    assert any("ocr_low_confidence_fallback" in issue for issue in result["issues"])


def test_no_ocr_engine_routes_everything_to_vlm(monkeypatch):
    monkeypatch.setattr(document_router, "get_ocr_provider", lambda: None)
    monkeypatch.setattr(
        document_router, "extract_page_text",
        lambda img, mime_type="image/png": {"success": True, "text": "vlm only", "error": None},
    )

    result = document_router.route_and_extract_page(b"page-bytes", page_number=1)

    assert result["source"] == "vlm"
    assert result["original_text"] == "vlm only"


def test_also_extract_fields_uses_combined_call_when_escalating_to_vlm(monkeypatch):
    # also_extract_fields=True should skip the plain-transcription VLM call
    # in favor of the combined transcribe+extract one, on the *same*
    # escalation trigger as any other page (here: low OCR confidence).
    ocr_result = OcrPageResult(
        boxes=[_printed_box(conf=0.4) for _ in range(10)],
        full_text="low confidence garbage",
        overall_confidence=0.4,
        engine="tesseract",
    )
    monkeypatch.setattr(document_router, "get_ocr_provider", lambda: FakeOcrProvider(ocr_result))
    monkeypatch.setattr(
        document_router, "extract_page_text",
        lambda img, mime_type="image/png": (_ for _ in ()).throw(AssertionError("plain transcription should not be called")),
    )
    monkeypatch.setattr(
        document_router, "extract_page_text_and_fields",
        lambda img, mime_type="image/png": {
            "success": True, "text": "combined transcription",
            "extracted": {"owner_name": "Test Owner", "chain": []},
            "model_used": "gemini-3.5-flash-lite", "error": None,
        },
    )

    result = document_router.route_and_extract_page(b"page-bytes", page_number=1, also_extract_fields=True)

    assert result["source"] == "vlm"
    assert result["original_text"] == "combined transcription"
    assert result["structured_fields"] == {"owner_name": "Test Owner", "chain": []}


def test_also_extract_fields_stays_none_when_ocr_succeeds(monkeypatch):
    # also_extract_fields=True is harmless when the page never reaches the
    # VLM at all — there's nothing to combine, and no VLM call should
    # happen either way.
    ocr_result = OcrPageResult(
        boxes=[_printed_box() for _ in range(10)],
        full_text="ten printed words",
        overall_confidence=0.9,
        engine="tesseract",
    )
    monkeypatch.setattr(document_router, "get_ocr_provider", lambda: FakeOcrProvider(ocr_result))
    monkeypatch.setattr(document_router, "extract_page_text", lambda img, mime_type="image/png": (_ for _ in ()).throw(AssertionError("VLM should not be called")))
    monkeypatch.setattr(document_router, "extract_page_text_and_fields", lambda img, mime_type="image/png": (_ for _ in ()).throw(AssertionError("combined VLM call should not be called")))

    result = document_router.route_and_extract_page(b"page-bytes", page_number=1, also_extract_fields=True)

    assert result["source"] == "ocr"
    assert result["structured_fields"] is None


def test_also_extract_fields_default_false_uses_plain_transcription(monkeypatch):
    # Default behavior (every existing caller) is unaffected: plain
    # transcription, structured_fields always None.
    monkeypatch.setattr(document_router, "get_ocr_provider", lambda: None)
    monkeypatch.setattr(
        document_router, "extract_page_text",
        lambda img, mime_type="image/png": {"success": True, "text": "plain transcription", "error": None},
    )
    monkeypatch.setattr(
        document_router, "extract_page_text_and_fields",
        lambda img, mime_type="image/png": (_ for _ in ()).throw(AssertionError("combined call should not be used by default")),
    )

    result = document_router.route_and_extract_page(b"page-bytes", page_number=1)

    assert result["original_text"] == "plain transcription"
    assert result["structured_fields"] is None


def test_vlm_failure_returns_sentinel_text_not_raise(monkeypatch):
    monkeypatch.setattr(document_router, "get_ocr_provider", lambda: None)
    monkeypatch.setattr(
        document_router, "extract_page_text",
        lambda img, mime_type="image/png": {"success": False, "text": None, "error": "Gemini timeout"},
    )

    result = document_router.route_and_extract_page(b"page-bytes", page_number=3)

    assert result["page_number"] == 3
    assert "page extraction failed" in result["original_text"]
    assert any("vlm_error" in issue for issue in result["issues"])
