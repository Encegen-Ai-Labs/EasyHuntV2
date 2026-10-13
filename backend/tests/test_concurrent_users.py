"""Several lawyers using the app at once (the 5-6 user target).

These check the three ways concurrent use used to go wrong: one slow upload
freezing every other request, every batch getting its own extraction cap (so the
caps added up), and a rate-limited document being flagged instead of retried.
"""
import asyncio
import threading
import time

import httpx

from app.api.v1.documents import get_doc_service, get_pipeline_service
from app.dependencies.auth import get_current_user
from app.main import app
from app.services import pipeline_service as pipeline_module
from app.services.pipeline_service import PipelineService
from tests.test_document_processing import FakeCaseRepo, FakeDocRepo, FakeDocumentPageRepo, FakeFlagRepo


def _service():
    return PipelineService(FakeDocRepo(), FakeCaseRepo(), FakeFlagRepo(), FakeDocumentPageRepo())


def test_extraction_cap_is_shared_by_every_batch(monkeypatch):
    service = _service()
    lock = threading.Lock()
    running = {"now": 0, "peak": 0}

    def fake_execute(doc_id):
        with lock:
            running["now"] += 1
            running["peak"] = max(running["peak"], running["now"])
        time.sleep(0.05)
        with lock:
            running["now"] -= 1
        return {"status": "success", "document_id": doc_id}

    monkeypatch.setattr(service, "execute_analysis_pipeline", fake_execute)

    async def six_users_at_once():
        # Six separate batches of 20, as six lawyers uploading together would queue.
        await asyncio.gather(*(
            service.execute_batch([f"u{user}-doc{n}" for n in range(20)]) for user in range(6)
        ))

    asyncio.run(six_users_at_once())

    assert 1 <= running["peak"] <= pipeline_module.MAX_CONCURRENT_EXTRACTIONS


def test_rate_limited_document_is_retried_not_flagged(monkeypatch):
    monkeypatch.setattr(pipeline_module, "IN_PROCESS_RATE_LIMIT_BACKOFF_SECONDS", 0)
    service = _service()
    attempts = []

    def fake_execute(doc_id):
        attempts.append(doc_id)
        if len(attempts) < 3:
            return {"status": "failed", "document_id": doc_id, "error": "429", "rate_limited": True}
        return {"status": "success", "document_id": doc_id}

    monkeypatch.setattr(service, "execute_analysis_pipeline", fake_execute)
    asyncio.run(service.execute_batch(["doc-1"]))

    assert len(attempts) == 3
    # Put back to "processing" between tries so the lawyer sees it still working.
    assert ("doc-1", "processing") in service.doc_repo.updated_statuses
    assert ("doc-1", "flagged") not in service.doc_repo.updated_statuses


def test_rate_limit_retries_stop_eventually(monkeypatch):
    monkeypatch.setattr(pipeline_module, "IN_PROCESS_RATE_LIMIT_BACKOFF_SECONDS", 0)
    service = _service()
    attempts = []

    def always_limited(doc_id):
        attempts.append(doc_id)
        return {"status": "failed", "document_id": doc_id, "error": "429", "rate_limited": True}

    monkeypatch.setattr(service, "execute_analysis_pipeline", always_limited)
    asyncio.run(service.execute_batch(["doc-1"]))

    assert len(attempts) == pipeline_module.IN_PROCESS_RATE_LIMIT_RETRIES + 1


class _SlowDocService:
    """Stands in for DocumentService: storing a file takes a while, like a real upload."""

    def authorize_case_access(self, case_id, current_user):
        return {"id": case_id}

    def upload_file(self, case_id, file_name, file_bytes, mime_type, current_user):
        time.sleep(0.4)
        return {
            "id": "11111111-1111-1111-1111-111111111111", "case_id": case_id, "file_name": file_name,
            "file_path": "x", "file_size": len(file_bytes), "mime_type": mime_type,
            "status": "uploaded", "created_at": "2026-08-01T00:00:00Z",
        }


class _NoopPipeline:
    async def execute_batch(self, doc_ids, force_refresh=False):
        pass


def test_a_slow_upload_does_not_freeze_other_requests(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", False)
    app.dependency_overrides[get_current_user] = lambda: {"id": "reviewer-1", "role": "Reviewer"}
    app.dependency_overrides[get_doc_service] = lambda: _SlowDocService()
    app.dependency_overrides[get_pipeline_service] = lambda: _NoopPipeline()
    try:
        async def scenario():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                files = [("files", (f"d{n}.pdf", b"%PDF-1.4 x", "application/pdf")) for n in range(5)]
                finished = asyncio.Event()
                worst_stall = 0.0

                async def watch_event_loop():
                    # Wakes every 10ms. If something blocks the loop, the gap between
                    # wake-ups is how long every other user would have been frozen.
                    nonlocal worst_stall
                    last = time.monotonic()
                    while not finished.is_set():
                        await asyncio.sleep(0.01)
                        now = time.monotonic()
                        worst_stall = max(worst_stall, now - last - 0.01)
                        last = now

                watcher = asyncio.create_task(watch_event_loop())
                response = await client.post(
                    "/api/v1/documents/upload",
                    data={"case_id": "22222222-2222-2222-2222-222222222222"},
                    files=files,
                )
                finished.set()
                await watcher
                return response.status_code, worst_stall

        upload_status, worst_stall = asyncio.run(scenario())
    finally:
        app.dependency_overrides.clear()

    assert upload_status == 201
    # Storing 5 files takes ~2s in total. Run on the event loop, that is one 0.4s+
    # stall per file; in the threadpool the loop keeps ticking.
    assert worst_stall < 0.25


class _Query:
    def __init__(self, rows, log):
        self.rows, self.log = rows, log

    def select(self, *_):
        return self

    def in_(self, column, values):
        self.log.append(("in_", column, list(values)))
        self.rows = [r for r in self.rows if r[column] in values]
        return self

    def order(self, *_):
        return self

    def execute(self):
        return type("R", (), {"data": self.rows})()


def test_review_listing_uses_one_extraction_query_for_the_whole_case():
    from app.services.review_service import ReviewService

    docs = [{"id": f"d{n}", "file_path": f"cases/c/d{n}.pdf", "status": "flagged"} for n in range(20)]
    extractions = [{"id": n, "document_id": f"d{n}", "has_handwritten_content": n == 3} for n in range(20)]
    log = []

    class Bucket:
        def create_signed_url(self, path, seconds):
            return {"signedURL": f"https://signed/{path}"}

    client = type("C", (), {})()
    client.table = lambda name: _Query(list(extractions), log)
    client.storage = type("S", (), {"from_": staticmethod(lambda bucket: Bucket())})()
    doc_repo = type("D", (), {"client": client, "list_reviewable_by_case": lambda self, cid: docs})()
    case_repo = type("K", (), {"get_by_id": lambda self, cid: {"id": cid}})()

    service = ReviewService(case_repo, None, doc_repo, extraction_repo=type("E", (), {"client": client})())
    result = service.get_case_documents_for_review("c")

    assert len(log) == 1  # one query, not one per document
    assert [r["document"]["id"] for r in result] == [f"d{n}" for n in range(20)]  # order kept
    assert result[5]["file_url"] == "https://signed/cases/c/d5.pdf"
    assert result[3]["extraction"]["handwriting_flagged"] is True
    assert result[4]["extraction"]["handwriting_flagged"] is False
