"""document_dispatch + the two routes that use it (/documents/upload and
/documents/{id}/process): a document must never be left in "processing" when
the queue is unavailable."""
import logging
import sys
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.v1.documents import get_doc_service, get_pipeline_service
from app.dependencies.auth import get_current_user
from app.main import app
from app.services import document_dispatch
from app.services.document_dispatch import (
    MODE_FAILED,
    MODE_FALLBACK,
    MODE_IN_PROCESS,
    MODE_QUEUED,
    DispatchOutcome,
    dispatch_documents,
)

CASE_ID = "22222222-2222-2222-2222-222222222222"
DOC_A = "11111111-1111-1111-1111-111111111111"
DOC_B = "33333333-3333-3333-3333-333333333333"


class FakeRepo:
    def __init__(self, fail=False):
        self.statuses = []
        self.fail = fail

    def update_status(self, document_id, status):
        if self.fail:
            raise RuntimeError("db down")
        self.statuses.append((document_id, status))


class FakePipeline:
    def __init__(self, repo=None):
        self.doc_repo = repo or FakeRepo()
        self.batches = []

    async def execute_batch(self, doc_ids):
        self.batches.append(list(doc_ids))


class FakeBackground:
    def __init__(self):
        self.tasks = []

    def add_task(self, fn, *args):
        self.tasks.append((fn, args))


class FakeTask:
    """Stands in for process_document_task; fails .delay() for chosen ids."""

    def __init__(self, fail_ids=()):
        self.fail_ids = set(fail_ids)
        self.delayed = []

    def delay(self, document_id):
        if document_id in self.fail_ids:
            raise ConnectionError("Error 111 connecting to redis:6379. Connection refused.")
        self.delayed.append(document_id)


def _queue_on(monkeypatch, task=None, importable=True):
    monkeypatch.setattr(document_dispatch.settings, "CELERY_ENABLED", True)
    module = SimpleNamespace(process_document_task=task) if importable else None
    # None in sys.modules makes `import` raise ImportError, as if celery were absent.
    monkeypatch.setitem(sys.modules, "app.tasks.document_tasks", module)


def _queue_off(monkeypatch):
    monkeypatch.setattr(document_dispatch.settings, "CELERY_ENABLED", False)
    # Prove the queue-off path never imports the task module (or celery).
    monkeypatch.setitem(sys.modules, "app.tasks.document_tasks", None)


# ---------- dispatch_documents ----------

def test_queue_off_runs_in_process_without_importing_celery(monkeypatch):
    _queue_off(monkeypatch)
    pipeline, background = FakePipeline(), FakeBackground()

    outcome = dispatch_documents([DOC_A, DOC_B], pipeline, background)

    assert outcome.mode == MODE_IN_PROCESS and outcome.warning is None
    assert background.tasks == [(pipeline.execute_batch, ([DOC_A, DOC_B],))]


def test_queue_on_enqueues_every_document_and_does_not_also_run_in_process(monkeypatch):
    task = FakeTask()
    _queue_on(monkeypatch, task)
    pipeline, background = FakePipeline(), FakeBackground()

    outcome = dispatch_documents([DOC_A, DOC_B], pipeline, background)

    assert outcome.mode == MODE_QUEUED and outcome.warning is None
    assert task.delayed == [DOC_A, DOC_B]
    assert background.tasks == []  # one path per upload, never both


def test_unreachable_broker_falls_back_in_process_loudly(monkeypatch, caplog):
    task = FakeTask(fail_ids={DOC_B})
    _queue_on(monkeypatch, task)
    pipeline, background = FakePipeline(), FakeBackground()

    with caplog.at_level(logging.ERROR):
        outcome = dispatch_documents([DOC_A, DOC_B], pipeline, background)

    assert outcome.mode == MODE_FALLBACK
    assert outcome.queued_ids == [DOC_A] and outcome.fallback_ids == [DOC_B]
    assert "queue is unavailable" in outcome.warning
    assert background.tasks == [(pipeline.execute_batch, ([DOC_B],))]
    assert pipeline.doc_repo.statuses == []  # not flagged: it is being processed
    assert any("QUEUE_UNAVAILABLE_FALLING_BACK_IN_PROCESS" in r.getMessage() for r in caplog.records)
    assert any("Connection refused" in r.getMessage() for r in caplog.records)


def test_celery_not_installed_falls_back_for_every_document(monkeypatch):
    _queue_on(monkeypatch, importable=False)
    pipeline, background = FakePipeline(), FakeBackground()

    outcome = dispatch_documents([DOC_A, DOC_B], pipeline, background)

    assert outcome.mode == MODE_FALLBACK and outcome.fallback_ids == [DOC_A, DOC_B]
    assert background.tasks == [(pipeline.execute_batch, ([DOC_A, DOC_B],))]


def test_no_fallback_possible_flags_the_documents(monkeypatch):
    _queue_on(monkeypatch, FakeTask(fail_ids={DOC_A, DOC_B}))
    pipeline = FakePipeline()

    outcome = dispatch_documents([DOC_A, DOC_B], pipeline, None)

    assert outcome.mode == MODE_FAILED and outcome.failed_ids == [DOC_A, DOC_B]
    assert pipeline.doc_repo.statuses == [(DOC_A, "flagged"), (DOC_B, "flagged")]


def test_failure_to_flag_is_logged_not_raised(monkeypatch):
    _queue_on(monkeypatch, FakeTask(fail_ids={DOC_A}))
    pipeline = FakePipeline(FakeRepo(fail=True))

    outcome = dispatch_documents([DOC_A], pipeline, None)

    assert outcome.mode == MODE_FAILED


def test_queue_off_without_executor_flags_documents(monkeypatch):
    _queue_off(monkeypatch)
    pipeline = FakePipeline()

    outcome = dispatch_documents([DOC_A], pipeline, None)

    assert outcome.mode == MODE_FAILED
    assert pipeline.doc_repo.statuses == [(DOC_A, "flagged")]


def test_nothing_to_dispatch_is_a_noop(monkeypatch):
    _queue_on(monkeypatch, FakeTask())
    assert dispatch_documents([], FakePipeline(), FakeBackground()).mode == MODE_IN_PROCESS


# ---------- routes ----------

def _login():
    app.dependency_overrides[get_current_user] = lambda: {"id": "reviewer-1", "role": "Reviewer"}


def teardown_function():
    app.dependency_overrides.clear()


class StubDocService:
    def authorize_case_access(self, case_id, current_user):
        return None

    def upload_file(self, case_id, file_name, file_bytes, mime_type, current_user):
        return {
            "id": DOC_A, "case_id": case_id, "file_name": file_name,
            "file_path": f"cases/{case_id}/{file_name}", "file_size": len(file_bytes),
            "mime_type": mime_type, "status": "uploaded", "created_at": "2026-08-01T00:00:00Z",
        }


def _upload(client):
    return client.post(
        "/api/v1/documents/upload",
        data={"case_id": CASE_ID},
        files=[("files", ("deed.pdf", b"%PDF-1.4", "application/pdf"))],
        headers={"Authorization": "Bearer test"},
    )


def test_upload_route_reports_fallback_and_runs_pipeline_in_process(monkeypatch):
    _login()
    _queue_on(monkeypatch, FakeTask(fail_ids={DOC_A}))
    pipeline = FakePipeline()
    app.dependency_overrides[get_doc_service] = lambda: StubDocService()
    app.dependency_overrides[get_pipeline_service] = lambda: pipeline

    response = _upload(TestClient(app))

    body = response.json()
    assert response.status_code == 201
    assert body["processing_mode"] == MODE_FALLBACK
    assert "queue is unavailable" in body["warning"]
    assert body["results"][0]["success"] is True and body["results"][0]["error"] is None
    assert pipeline.batches == [[DOC_A]]  # the background task actually ran


def test_upload_route_marks_result_when_documents_could_not_be_started(monkeypatch):
    _login()
    app.dependency_overrides[get_doc_service] = lambda: StubDocService()
    app.dependency_overrides[get_pipeline_service] = lambda: FakePipeline()
    monkeypatch.setattr(
        "app.api.v1.documents.dispatch_documents",
        lambda ids, pipeline, background: DispatchOutcome(
            mode=MODE_FAILED, failed_ids=list(ids), warning="queue down, flagged"
        ),
    )

    body = _upload(TestClient(app)).json()

    assert body["processing_mode"] == MODE_FAILED and body["warning"] == "queue down, flagged"
    assert "could not be started" in body["results"][0]["error"]


def test_upload_route_queue_off_uses_the_in_process_path(monkeypatch):
    _login()
    _queue_off(monkeypatch)
    pipeline = FakePipeline()
    app.dependency_overrides[get_doc_service] = lambda: StubDocService()
    app.dependency_overrides[get_pipeline_service] = lambda: pipeline

    body = _upload(TestClient(app)).json()

    assert body["processing_mode"] == MODE_IN_PROCESS and body["warning"] is None
    assert pipeline.batches == [[DOC_A]]


def test_process_route_queues_when_the_broker_is_up(monkeypatch):
    _login()
    task = FakeTask()
    _queue_on(monkeypatch, task)
    app.dependency_overrides[get_pipeline_service] = lambda: FakePipeline()

    response = TestClient(app).post(
        f"/api/v1/documents/{DOC_A}/process", headers={"Authorization": "Bearer test"}
    )

    assert response.status_code == 200
    assert response.json()["processing_mode"] == MODE_QUEUED
    assert task.delayed == [DOC_A]


def test_process_route_falls_back_in_process_when_the_broker_is_down(monkeypatch):
    _login()
    _queue_on(monkeypatch, FakeTask(fail_ids={DOC_A}))
    pipeline = FakePipeline()
    app.dependency_overrides[get_pipeline_service] = lambda: pipeline

    response = TestClient(app).post(
        f"/api/v1/documents/{DOC_A}/process", headers={"Authorization": "Bearer test"}
    )

    body = response.json()
    assert response.status_code == 200
    assert body["processing_mode"] == MODE_FALLBACK and "queue is unavailable" in body["warning"]
    assert pipeline.batches == [[DOC_A]]


def test_process_route_returns_503_when_nothing_could_start_it(monkeypatch):
    _login()
    app.dependency_overrides[get_pipeline_service] = lambda: FakePipeline()
    monkeypatch.setattr(
        "app.api.v1.documents.dispatch_documents",
        lambda ids, pipeline, background: DispatchOutcome(
            mode=MODE_FAILED, failed_ids=list(ids), warning="queue down, flagged"
        ),
    )

    response = TestClient(app).post(
        f"/api/v1/documents/{DOC_A}/process", headers={"Authorization": "Bearer test"}
    )

    assert response.status_code == 503
