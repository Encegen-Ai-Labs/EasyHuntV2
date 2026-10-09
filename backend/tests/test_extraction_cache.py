"""Extraction cache: keys, stores, and how the pipeline uses it."""
import json
from types import SimpleNamespace

import pytest

from app.services import document_dispatch, extraction_cache as ec
from app.services.extraction_cache import (
    CACHED_RESULT_PREFIX, ExtractionCache, FileCacheStore, SupabaseCacheStore, make_key,
    pages_are_cacheable, sha256_bytes,
)
from app.services.pipeline_service import PipelineService

from test_document_processing import (
    FakeCaseRepo, FakeDocRepo, FakeDocumentPageRepo, FakeFlagRepo,
)

GOOD_PAGE = {"page_number": 1, "original_text": "text", "source": "vlm", "confidence": None,
             "has_handwriting": False, "issues": [], "structured_fields": None}
OK_RESULT = {"success": True, "extracted": {"owner_name": "A"}, "model_used": "m"}


# ------------------------------------------------------------ pure pieces

def test_key_depends_on_each_component():
    base = make_key("sha", "model", "v1")
    assert base == make_key("sha", "model", "v1")
    assert len({base, make_key("sha2", "model", "v1"), make_key("sha", "model2", "v1"),
                make_key("sha", "model", "v2")}) == 4


def test_pipeline_version_is_stable_and_short():
    v = ec.pipeline_version()
    assert v == ec.pipeline_version() and len(v) == 12


def test_pipeline_version_changes_when_a_prompt_changes(monkeypatch):
    from app.services import llm_extractor
    before = ec.pipeline_version()
    ec.pipeline_version.cache_clear()
    monkeypatch.setattr(llm_extractor, "STRUCTURED_EXTRACTION_FROM_TEXT_PROMPT", "a different prompt")
    try:
        assert ec.pipeline_version() != before
    finally:
        ec.pipeline_version.cache_clear()


def test_pages_cacheable_rules():
    assert pages_are_cacheable([GOOD_PAGE])
    assert not pages_are_cacheable([GOOD_PAGE, {**GOOD_PAGE, "source": "error"}])
    assert not pages_are_cacheable([{**GOOD_PAGE, "original_text": "[page extraction failed: 504]"}])
    assert not pages_are_cacheable([{**GOOD_PAGE, "issues": ["vlm_error: boom"]}])
    assert not pages_are_cacheable([None])


def test_file_store_round_trip_and_put_rules(tmp_path):
    cache = ExtractionCache(FileCacheStore(tmp_path), version="v1", model="m")
    assert cache.get("sha") is None
    assert cache.put("sha", [GOOD_PAGE], OK_RESULT) is True
    entry = cache.get("sha")
    assert entry["extracted"] == {"owner_name": "A"} and entry["routed_pages"] == [GOOD_PAGE]
    assert entry["created_at"]
    # a different version or model is a different key
    assert ExtractionCache(FileCacheStore(tmp_path), version="v2", model="m").get("sha") is None
    assert ExtractionCache(FileCacheStore(tmp_path), version="v1", model="m2").get("sha") is None


def test_failures_are_never_stored(tmp_path):
    cache = ExtractionCache(FileCacheStore(tmp_path), version="v1", model="m")
    failed = {"success": False, "error": "429", "rate_limited": True, "extracted": None}
    assert cache.put("sha", [GOOD_PAGE], failed) is False
    assert cache.put("sha", [{**GOOD_PAGE, "source": "error"}], OK_RESULT) is False
    assert cache.get("sha") is None


def test_store_errors_are_misses_not_exceptions():
    class Boom:
        def get(self, key): raise RuntimeError("relation extraction_cache does not exist")
        def put(self, row): raise RuntimeError("nope")
    cache = ExtractionCache(Boom(), version="v1", model="m")
    assert cache.get("sha") is None
    assert cache.put("sha", [GOOD_PAGE], OK_RESULT) is False


def test_malformed_entry_is_a_miss(tmp_path):
    store = FileCacheStore(tmp_path)
    cache = ExtractionCache(store, version="v1", model="m")
    store.put({"key": cache.key_for("sha"), "result": {"routed_pages": "oops"}})
    assert cache.get("sha") is None


def test_supabase_store_uses_upsert_and_select():
    calls = []

    class Q:
        def __init__(self): self.rows = [{"key": "k", "result": {}}]
        def select(self, *a): calls.append("select"); return self
        def eq(self, *a): calls.append(("eq", a)); return self
        def limit(self, n): return self
        def upsert(self, row, on_conflict=None): calls.append(("upsert", on_conflict)); return self
        def execute(self): return SimpleNamespace(data=self.rows)

    client = SimpleNamespace(table=lambda name: (calls.append(("table", name)), Q())[1])
    store = SupabaseCacheStore(client)
    assert store.get("k")["key"] == "k"
    store.put({"key": "k"})
    assert ("table", "extraction_cache") in calls and ("upsert", "key") in calls


def test_build_cache_off_by_default(monkeypatch):
    monkeypatch.setattr(ec.settings, "EXTRACTION_CACHE_ENABLED", False)
    assert ec.build_cache(object()) is None
    monkeypatch.setattr(ec.settings, "EXTRACTION_CACHE_ENABLED", True)
    assert isinstance(ec.build_cache(object()), ExtractionCache)


# --------------------------------------------------------- pipeline usage

class Counters:
    def __init__(self):
        self.routed = 0
        self.fields = 0
        self.enhanced = 0


def setup_pipeline(monkeypatch, tmp_path, file_bytes=b"file-bytes", pages=2, fields_ok=True, cache=True):
    doc_repo = FakeDocRepo({"id": "doc-1", "case_id": "case-1", "file_path": "cases/case-1/t.pdf", "status": "processing"})
    c = Counters()
    store = FileCacheStore(tmp_path / "cache")
    xc = ExtractionCache(store, version="v-test", model="m") if cache else None
    service = PipelineService(doc_repo, FakeCaseRepo({"id": "case-1", "created_by": "r"}), FakeFlagRepo(),
                              FakeDocumentPageRepo(), extraction_cache=xc)

    monkeypatch.setattr("app.services.pipeline_service.download_file", lambda url: file_bytes)
    monkeypatch.setattr("app.services.pipeline_service.rasterize_pages",
                        lambda b, m: [f"p{i}".encode() for i in range(pages)])
    monkeypatch.setattr("app.services.pipeline_service.download_and_rasterize",
                        lambda url, m: [f"p{i}".encode() for i in range(pages)])

    def enhance(img):
        c.enhanced += 1
        return img, {"fallback": False}
    monkeypatch.setattr("app.services.pipeline_service.enhance_page_image_with_report", enhance)

    def route(img, page_number, also_extract_fields=False):
        c.routed += 1
        return {"page_number": page_number, "original_text": f"text {page_number}", "source": "vlm",
                "confidence": None, "has_handwriting": False, "issues": [], "structured_fields": None}
    monkeypatch.setattr("app.services.pipeline_service.route_and_extract_page", route)

    def fields(text):
        c.fields += 1
        if not fields_ok:
            return {"success": False, "raw_output": None, "extracted": None, "model_used": "m",
                    "error": "429", "rate_limited": True}
        return {"success": True, "raw_output": "x", "extracted": {"chain": [], "owner_name": "Ramesh"},
                "model_used": "m", "error": None}
    monkeypatch.setattr("app.services.pipeline_service.extract_structured_fields_from_text", fields)
    return service, doc_repo, c, xc


def stored(doc_repo):
    return doc_repo._inserted[-1]


def run(service, repo, **kwargs):
    """Runs the pipeline as for a fresh document: the fake repo reports an
    extraction as already existing once one was inserted, which would
    short-circuit a second run (that is the per-document guard, separate
    from the content cache under test)."""
    repo._inserted.clear()
    return service.execute_analysis_pipeline("doc-1", **kwargs)


def test_second_run_on_same_bytes_makes_no_model_calls_and_same_output(monkeypatch, tmp_path):
    service, repo, c, _ = setup_pipeline(monkeypatch, tmp_path)
    run(service, repo)
    first = stored(repo)
    assert (c.routed, c.fields) == (2, 1)

    run(service, repo)
    second = stored(repo)
    assert (c.routed, c.fields) == (2, 1)  # no new model calls
    assert c.enhanced == 4                 # enhanced images are still produced and stored
    assert second["validated_json_output"] == first["validated_json_output"]
    assert second["raw_ocr_text"] == first["raw_ocr_text"]
    assert second["has_handwritten_content"] == first["has_handwritten_content"]
    assert second["model_used"] == first["model_used"]
    notes = [e for e in second["validation_errors"] if str(e).startswith(CACHED_RESULT_PREFIX)]
    assert len(notes) == 1
    assert not any(str(e).startswith(CACHED_RESULT_PREFIX) for e in first["validation_errors"])


def test_different_bytes_miss(monkeypatch, tmp_path):
    service, repo, c, xc = setup_pipeline(monkeypatch, tmp_path, file_bytes=b"A")
    run(service, repo)
    monkeypatch.setattr("app.services.pipeline_service.download_file", lambda url: b"B")
    run(service, repo)
    assert c.fields == 2


def test_force_refresh_bypasses_and_replaces_the_entry(monkeypatch, tmp_path):
    service, repo, c, xc = setup_pipeline(monkeypatch, tmp_path)
    run(service, repo)
    run(service, repo, force_refresh=True)
    assert (c.routed, c.fields) == (4, 2)
    assert not any(str(e).startswith(CACHED_RESULT_PREFIX) for e in stored(repo)["validation_errors"])
    # the fresh result is what a later normal run gets
    run(service, repo)
    assert (c.routed, c.fields) == (4, 2)


def test_failed_extraction_is_not_cached(monkeypatch, tmp_path):
    service, repo, c, xc = setup_pipeline(monkeypatch, tmp_path, fields_ok=False)
    result = service.execute_analysis_pipeline("doc-1")
    assert result["status"] == "failed" and result["rate_limited"] is True
    assert xc.get(sha256_bytes(b"file-bytes")) is None


def test_cache_off_keeps_the_original_download_path(monkeypatch, tmp_path):
    service, repo, c, _ = setup_pipeline(monkeypatch, tmp_path, cache=False)
    monkeypatch.setattr("app.services.pipeline_service.download_file",
                        lambda url: (_ for _ in ()).throw(AssertionError("must not be used when cache is off")))
    service.execute_analysis_pipeline("doc-1")
    assert service.extraction_cache is None and c.fields == 1
    assert not any(str(e).startswith(CACHED_RESULT_PREFIX) for e in stored(repo)["validation_errors"])


def test_page_count_mismatch_in_entry_is_a_miss(monkeypatch, tmp_path):
    service, repo, c, xc = setup_pipeline(monkeypatch, tmp_path, pages=2)
    xc.put(sha256_bytes(b"file-bytes"), [GOOD_PAGE], OK_RESULT)  # 1 page stored, file has 2
    service.execute_analysis_pipeline("doc-1")
    assert c.fields == 1


def test_broken_store_does_not_fail_the_document(monkeypatch, tmp_path):
    service, repo, c, xc = setup_pipeline(monkeypatch, tmp_path)

    class Boom:
        def get(self, key): raise RuntimeError("no such table")
        def put(self, row): raise RuntimeError("no such table")
    service.extraction_cache = ExtractionCache(Boom(), version="v", model="m")
    result = service.execute_analysis_pipeline("doc-1")
    assert result["status"] == "success" and c.fields == 1


# ------------------------------------------------------------- dispatch

class KwBackground:
    def __init__(self): self.tasks = []
    def add_task(self, fn, *args, **kwargs): self.tasks.append((fn, args, kwargs))


class Pipe:
    doc_repo = None
    async def execute_batch(self, ids, force_refresh=False): pass


def test_dispatch_default_call_shape_unchanged_and_force_is_passed(monkeypatch):
    monkeypatch.setattr(document_dispatch.settings, "CELERY_ENABLED", False)
    bg, p = KwBackground(), Pipe()
    document_dispatch.dispatch_documents(["a"], p, bg)
    document_dispatch.dispatch_documents(["a"], p, bg, force_refresh=True)
    assert bg.tasks[0][1:] == ((["a"],), {}) and bg.tasks[1][1:] == ((["a"],), {"force_refresh": True})


def test_dispatch_queue_passes_force_refresh(monkeypatch):
    import sys
    delayed = []
    task = SimpleNamespace(delay=lambda *a: delayed.append(a))
    monkeypatch.setattr(document_dispatch.settings, "CELERY_ENABLED", True)
    monkeypatch.setitem(sys.modules, "app.tasks.document_tasks", SimpleNamespace(process_document_task=task))
    document_dispatch.dispatch_documents(["a"], Pipe(), KwBackground())
    document_dispatch.dispatch_documents(["b"], Pipe(), KwBackground(), force_refresh=True)
    assert delayed == [("a",), ("b", True)]


# ------------------------------------------------------------ upload route

def test_upload_route_passes_force_refresh_only_when_requested(monkeypatch):
    from fastapi.testclient import TestClient
    from app.api.v1.documents import get_doc_service, get_pipeline_service
    from app.dependencies.auth import get_current_user
    from app.main import app
    from test_document_dispatch import CASE_ID, DOC_A, FakePipeline, StubDocService
    from app.services.document_dispatch import DispatchOutcome

    seen = []
    app.dependency_overrides[get_current_user] = lambda: {"id": "r", "role": "Reviewer"}
    app.dependency_overrides[get_doc_service] = lambda: StubDocService()
    app.dependency_overrides[get_pipeline_service] = lambda: FakePipeline()
    monkeypatch.setattr(
        "app.api.v1.documents.dispatch_documents",
        lambda ids, pipeline, background, **kw: (seen.append(kw), DispatchOutcome())[1],
    )
    try:
        client = TestClient(app)
        files = [("files", ("deed.pdf", b"%PDF-1.4", "application/pdf"))]
        hdr = {"Authorization": "Bearer test"}
        assert client.post("/api/v1/documents/upload", data={"case_id": CASE_ID}, files=files, headers=hdr).status_code == 201
        assert client.post("/api/v1/documents/upload", data={"case_id": CASE_ID, "force_refresh": "true"},
                           files=files, headers=hdr).status_code == 201
    finally:
        app.dependency_overrides.clear()
    assert seen == [{}, {"force_refresh": True}]
