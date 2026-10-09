import pytest

from app.services.rate_limit import RateLimited
from app.tasks import document_tasks
from app.tasks.document_tasks import backoff_seconds, process_document_task


class StubRepo:
    def __init__(self):
        self.statuses = []

    def update_status(self, document_id, status):
        self.statuses.append((document_id, status))


class StubPipeline:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.doc_repo = StubRepo()

    def execute_analysis_pipeline(self, document_id):
        assert document_id == "document-123"
        if self.error:
            raise self.error
        return self.result


class Retried(Exception):
    def __init__(self, exc, countdown):
        self.exc, self.countdown = exc, countdown


@pytest.fixture
def capture_retry(monkeypatch):
    def fake_retry(exc=None, countdown=None, **kw):
        raise Retried(exc, countdown)

    monkeypatch.setattr(process_document_task, "retry", fake_retry)


def _run_with_retries(retries):
    process_document_task.push_request(retries=retries)
    try:
        return process_document_task.run("document-123")
    finally:
        process_document_task.pop_request()


def test_document_task_runs_the_existing_pipeline(monkeypatch):
    stub = StubPipeline({"status": "success"})
    monkeypatch.setattr(document_tasks, "_pipeline_service", lambda: stub)

    result = process_document_task.run("document-123")

    assert result == {"document_id": "document-123", "status": "success"}


def test_rate_limited_document_is_retried_with_backoff(monkeypatch, capture_retry):
    stub = StubPipeline({"status": "failed", "rate_limited": True, "error": "429"})
    monkeypatch.setattr(document_tasks, "_pipeline_service", lambda: stub)

    with pytest.raises(Retried) as caught:
        _run_with_retries(0)

    base = document_tasks.settings.CELERY_RATE_LIMIT_BACKOFF_SECONDS
    assert isinstance(caught.value.exc, RateLimited)
    assert base <= caught.value.countdown <= base * 1.25
    # Shown as in progress while waiting, not stuck on the pipeline's "flagged".
    assert stub.doc_repo.statuses == [("document-123", "processing")]


def test_rate_limit_backoff_grows_with_each_attempt(monkeypatch, capture_retry):
    monkeypatch.setattr(
        document_tasks, "_pipeline_service",
        lambda: StubPipeline({"status": "failed", "rate_limited": True}),
    )
    with pytest.raises(Retried) as first:
        _run_with_retries(0)
    with pytest.raises(Retried) as third:
        _run_with_retries(2)
    assert third.value.countdown > first.value.countdown


def test_rate_limited_document_gives_up_after_the_retry_budget(monkeypatch, capture_retry):
    stub = StubPipeline({"status": "failed", "rate_limited": True, "error": "429"})
    monkeypatch.setattr(document_tasks, "_pipeline_service", lambda: stub)

    result = _run_with_retries(document_tasks.settings.CELERY_RATE_LIMIT_RETRIES)

    assert result == {"document_id": "document-123", "status": "failed"}
    assert stub.doc_repo.statuses == []  # stays flagged, as the pipeline left it


def test_ordinary_pipeline_failure_is_not_retried(monkeypatch, capture_retry):
    stub = StubPipeline({"status": "failed", "rate_limited": False, "error": "bad pdf"})
    monkeypatch.setattr(document_tasks, "_pipeline_service", lambda: stub)

    assert _run_with_retries(0)["status"] == "failed"


def test_unexpected_exception_retries_then_flags_the_document(monkeypatch, capture_retry):
    stub = StubPipeline(error=RuntimeError("db blip"))
    monkeypatch.setattr(document_tasks, "_pipeline_service", lambda: stub)

    with pytest.raises(Retried):
        _run_with_retries(0)

    with pytest.raises(RuntimeError):
        _run_with_retries(document_tasks.UNEXPECTED_FAILURE_RETRIES)
    assert stub.doc_repo.statuses == [("document-123", "flagged")]


def test_backoff_seconds_is_exponential_with_bounded_jitter():
    for attempt in range(4):
        delay = backoff_seconds(10, attempt)
        assert 10 * 2 ** attempt <= delay <= 10 * 2 ** attempt * 1.25
