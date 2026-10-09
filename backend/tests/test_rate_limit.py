"""Rate-limit labelling must be purely additive: extraction output on success
(and every existing failure shape) stays exactly as it was, and the
has_handwritten_content missing-means-True default is untouched."""
import json

from app.services import llm_extractor, page_extraction_service as page_svc
from app.services.rate_limit import is_rate_limit_error
from app.services.validation import validate_extraction

SUCCESS_KEYS = {"success", "raw_output", "extracted", "model_used", "error"}
PAGE_FIELD_KEYS = {"success", "text", "extracted", "model_used", "error"}


class _ApiError(Exception):
    def __init__(self, code, message="boom", status=None):
        super().__init__(message)
        self.code = code
        self.status = status


class _Response:
    def __init__(self, text):
        self.text = text


def test_is_rate_limit_error_recognizes_429_and_resource_exhausted():
    assert is_rate_limit_error(_ApiError(429))
    assert is_rate_limit_error(_ApiError(None, status="RESOURCE_EXHAUSTED"))
    assert is_rate_limit_error(Exception("429 RESOURCE_EXHAUSTED: quota"))
    assert not is_rate_limit_error(_ApiError(503))
    assert not is_rate_limit_error(Exception("Model returned invalid JSON"))
    assert not is_rate_limit_error(None)


def test_structured_extraction_success_shape_is_unchanged(monkeypatch):
    payload = {"owner_name": "A", "has_handwritten_content": False}
    monkeypatch.setattr(
        llm_extractor.client_genai.models, "generate_content",
        lambda **kw: _Response(json.dumps(payload)),
    )
    result = llm_extractor.extract_structured_fields_from_text("text")
    assert set(result) == SUCCESS_KEYS
    assert result["success"] is True and result["extracted"] == payload


def test_structured_extraction_invalid_json_shape_is_unchanged(monkeypatch):
    monkeypatch.setattr(
        llm_extractor.client_genai.models, "generate_content", lambda **kw: _Response("not json")
    )
    result = llm_extractor.extract_structured_fields_from_text("text")
    assert set(result) == SUCCESS_KEYS
    assert result["success"] is False and result["error"] == "Model returned invalid JSON"


def test_structured_extraction_labels_429_only(monkeypatch):
    def boom(**kw):
        raise _ApiError(429)

    monkeypatch.setattr(llm_extractor.client_genai.models, "generate_content", boom)
    assert llm_extractor.extract_structured_fields_from_text("t")["rate_limited"] is True

    def other(**kw):
        raise _ApiError(500)

    monkeypatch.setattr(llm_extractor.client_genai.models, "generate_content", other)
    assert llm_extractor.extract_structured_fields_from_text("t")["rate_limited"] is False


def test_page_extraction_success_shapes_are_unchanged(monkeypatch):
    monkeypatch.setattr(
        page_svc.client_genai.models, "generate_content", lambda **kw: _Response("  page text  ")
    )
    assert page_svc.extract_page_text(b"img") == {"success": True, "text": "page text", "error": None}


def test_page_extraction_labels_429(monkeypatch):
    def boom(**kw):
        raise _ApiError(429)

    monkeypatch.setattr(page_svc.client_genai.models, "generate_content", boom)
    assert page_svc.extract_page_text(b"img")["rate_limited"] is True
    combined = page_svc.extract_page_text_and_fields(b"img")
    assert combined["rate_limited"] is True and PAGE_FIELD_KEYS <= set(combined)


def test_missing_has_handwritten_content_still_means_handwritten():
    result = validate_extraction({})
    assert result["reason_handwritten"] is True
    assert any("handwritten" in w for w in result["warnings"])
    assert validate_extraction({"has_handwritten_content": False})["reason_handwritten"] is False
