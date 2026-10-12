import json
import logging

from app.core import context
from app.core.logging import RedactingJsonFormatter, RedactingTextFormatter


def _record(message, *args, exc_info=None):
    return logging.LogRecord("property_verification", logging.INFO, __file__, 1, message, args, exc_info)


def test_json_line_splits_the_event_and_key_values_and_adds_context():
    context.bind(request_id="req-1", document_id="doc-9")
    try:
        line = json.loads(RedactingJsonFormatter().format(_record("pipeline.rasterized | document_id=%s pages=%s", "doc-9", 3)))
    finally:
        context.bind(request_id=None, document_id=None)

    assert line["event"] == "pipeline.rasterized" and line["pages"] == "3"
    assert line["request_id"] == "req-1" and line["document_id"] == "doc-9" and line["level"] == "INFO"


def test_secrets_never_reach_the_json_line_or_the_traceback(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "super-secret-gemini-key-000")
    try:
        raise RuntimeError("call failed for url https://x.test?key=AQ.abcdefghijklmnopqrstuvwxyz and super-secret-gemini-key-000")
    except RuntimeError:
        import sys
        out = RedactingJsonFormatter().format(_record("boom", exc_info=sys.exc_info()))

    assert "super-secret-gemini-key-000" not in out and "abcdefghijklmnopqrstuvwxyz" not in out


def test_text_format_is_redacted_too(monkeypatch):
    monkeypatch.setenv("GOOGLE_TRANSLATE_API_KEY", "translate-key-value-abcdef")
    out = RedactingTextFormatter("%(levelname)s: %(message)s").format(_record("failed with translate-key-value-abcdef"))
    assert "translate-key-value-abcdef" not in out
