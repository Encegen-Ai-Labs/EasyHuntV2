import logging

from fastapi.testclient import TestClient

from app.core import context
from app.core.error_store import ErrorStoreHandler
from app.dependencies.auth import get_current_user
from app.dependencies.db import get_supabase_service_client
from app.main import app


def _handler(monkeypatch):
    handler = ErrorStoreHandler()
    monkeypatch.setattr(handler, "_ensure_worker", lambda: None)  # no background thread in tests
    return handler


def _record(message, level=logging.ERROR, exc=None):
    return logging.LogRecord("property_verification", level, __file__, 1, message, (), exc)


def test_an_error_is_queued_with_who_and_what_and_without_secrets(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key-secret-value-123")
    handler = _handler(monkeypatch)
    context.bind(request_id="req-1", document_id="doc-9", case_id="case-3")
    try:
        handler.emit(_record("doc_service.upload_failed | document_id=doc-9 error=denied gemini-key-secret-value-123"))
    finally:
        context.bind(request_id=None, document_id=None, case_id=None)

    row = handler._queue.get_nowait()
    assert row["event"] == "doc_service.upload_failed"
    assert row["document_id"] == "doc-9" and row["case_id"] == "case-3" and row["request_id"] == "req-1"
    assert "gemini-key-secret-value-123" not in row["message"]


def test_only_errors_are_kept():
    handler = ErrorStoreHandler()
    assert handler.level == logging.ERROR


def test_a_full_queue_drops_the_record_instead_of_raising(monkeypatch):
    handler = _handler(monkeypatch)
    monkeypatch.setattr(handler, "_queue", __import__("queue").Queue(maxsize=1))
    handler.emit(_record("one"))
    handler.emit(_record("two"))  # must not raise
    assert handler._queue.qsize() == 1


class _Query:
    def __init__(self, rows=None, fail=False):
        self.rows, self.fail = rows or [], fail

    def select(self, *a, **k):
        return self

    def order(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def execute(self):
        if self.fail:
            raise RuntimeError('relation "app_errors" does not exist')
        return type("R", (), {"data": self.rows})()


class _Db:
    def __init__(self, query):
        self.query = query

    def table(self, name):
        return self.query


def _get(role, query):
    app.dependency_overrides[get_current_user] = lambda: {"id": "u1", "role": role}
    app.dependency_overrides[get_supabase_service_client] = lambda: _Db(query)
    try:
        return TestClient(app).get("/api/v1/admin/errors")
    finally:
        app.dependency_overrides.clear()


def test_admin_sees_recent_errors():
    response = _get("Admin", _Query([{"created_at": "t", "event": "doc_service.upload_failed", "message": "m"}]))
    assert response.status_code == 200 and response.json()["errors"][0]["event"] == "doc_service.upload_failed"


def test_a_lawyer_cannot_read_the_error_list():
    assert _get("Reviewer", _Query()).status_code == 403


def test_a_missing_table_gives_a_clear_message():
    response = _get("Admin", _Query(fail=True))
    assert response.status_code == 503 and "0011_app_errors.sql" in response.json()["detail"] and "relation" not in response.text
