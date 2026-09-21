import asyncio

import pytest

from app.core.exceptions import PermissionDeniedError, ResourceNotFoundError
from app.services.doc_service import DocumentService
from app.services.pipeline_service import PipelineService
from app.services.review_service import ReviewService


class FakeCaseRepo:
    def __init__(self, case_obj=None):
        self.case_obj = case_obj or {"id": "case-1", "created_by": "reviewer-1"}
        self.updated_cases = []

    def get_by_id(self, case_id):
        return self.case_obj if self.case_obj.get("id") == case_id else None

    def update_case(self, case_id, case_data):
        self.updated_cases.append((case_id, case_data))
        self.case_obj.update(case_data)
        return self.case_obj


class FakeDocRepo:
    def __init__(self, doc=None):
        self.doc = doc or {
            "id": "doc-1",
            "case_id": "case-1",
            "file_path": "cases/case-1/test.pdf",
            "status": "processing",
        }
        self.updated_statuses = []
        self.client = type("Client", (), {})()
        self.client.storage = type("Storage", (), {})()
        self.client.storage.from_ = lambda bucket: type("Bucket", (), {"upload": self._upload, "create_signed_url": self._create_signed_url})()
        self.client.table = lambda table: self
        self._inserted = []
        self.uploaded = []

    def insert(self, data):
        self._inserted.append(data)
        return self

    def select(self, columns):
        return self

    def eq(self, key, value):
        return self

    def update(self, data):
        return self

    def execute(self):
        data = [self._inserted[-1]] if self._inserted else []
        return type("Response", (), {"data": data})()
    def _upload(self, path, file, file_options=None):
        self.uploaded.append((path, file, file_options))
        return {"path": path}

    def _create_signed_url(self, path, ttl):
        return {"signedURL": "https://example.com/file.pdf"}

    def create_document(self, doc_payload):
        self.doc = {**self.doc, **doc_payload}
        return self.doc

    def get_by_id(self, doc_id):
        return self.doc if self.doc.get("id") == doc_id else None

    def update_status(self, doc_id, status):
        self.updated_statuses.append((doc_id, status))
        self.doc["status"] = status
        return self.doc

    def list_reviewable_by_case(self, case_id):
        return [self.doc] if self.doc.get("case_id") == case_id and self.doc.get("status") in {
            "llm_done", "flagged", "under_review"
        } else []


class FakeFlagRepo:
    def __init__(self):
        self.flags = []

    def create_flag(self, payload):
        self.flags.append(payload)
        return payload

    def update_flag(self, flag_id, payload):
        return {"id": flag_id, **payload}


class FakeDocumentPageRepo:
    def __init__(self):
        self.created_pages = []

    def bulk_create(self, pages):
        self.created_pages.extend(pages)
        return pages


class FakeDocumentRepoForReview(FakeDocRepo):
    def list_by_case(self, case_id):
        return [self.doc] if self.doc.get("case_id") == case_id else []


class FakeExtractionRepo:
    def __init__(self, extraction=None):
        self.extraction = extraction or {
            "id": "extraction-1",
            "document_id": "doc-1",
            "validated_json_output": {"survey_number": "SY-1"},
            "has_handwritten_content": True,
        }
        self.updated = []

    def select_one(self, table, filters):
        return self.extraction if filters.get("document_id") == self.extraction["document_id"] else None

    def update(self, table, filters, payload):
        self.updated.append((table, filters, payload))
        self.extraction.update(payload)
        return [self.extraction]


def test_validate_and_upload_returns_processing_status_and_metadata():
    case_repo = FakeCaseRepo()
    doc_repo = FakeDocRepo()
    service = DocumentService(doc_repo, case_repo)

    result = service.validate_and_upload(
        case_id="case-1",
        file_name="test.pdf",
        file_bytes=b"demo",
        mime_type="application/pdf",
        current_user={"id": "reviewer-1", "role": "Reviewer"},
    )

    assert result["status"] == "processing"
    assert result["file_path"] == "cases/case-1/test.pdf"
    assert result["id"] == "doc-1"


def test_authorize_case_access_then_upload_file_matches_validate_and_upload():
    # Batch upload calls authorize_case_access() once, then upload_file() per file,
    # instead of validate_and_upload()'s single-file all-in-one call — both paths
    # must produce the same result.
    case_repo = FakeCaseRepo()
    doc_repo = FakeDocRepo()
    service = DocumentService(doc_repo, case_repo)
    current_user = {"id": "reviewer-1", "role": "Reviewer"}

    service.authorize_case_access("case-1", current_user)
    result = service.upload_file("case-1", "test.pdf", b"demo", "application/pdf", current_user)

    assert result["status"] == "processing"
    assert result["file_path"] == "cases/case-1/test.pdf"


def test_authorize_case_access_blocks_unrelated_reviewer():
    case_repo = FakeCaseRepo({"id": "case-1", "created_by": "reviewer-1"})
    doc_repo = FakeDocRepo()
    service = DocumentService(doc_repo, case_repo)

    with pytest.raises(PermissionDeniedError):
        service.authorize_case_access("case-1", {"id": "someone-else", "role": "Reviewer"})


class _FakeDeleteClient:
    """Minimal fake Supabase client for delete_document — tracks which
    tables were deleted from (with what .eq() filters) and which storage
    paths were removed. Kept separate from FakeDocRepo's own client (which
    doesn't track table names or support delete/remove) so this doesn't
    change behavior for the tests already relying on that fixture."""
    def __init__(self):
        self.deleted = []  # [(table, {filter_key: filter_value})]
        self.removed_paths = []
        self._table = None
        self._filters = {}

    def table(self, name):
        self._table = name
        self._filters = {}
        return self

    def delete(self):
        return self

    def eq(self, key, value):
        self._filters[key] = value
        return self

    def execute(self):
        self.deleted.append((self._table, dict(self._filters)))
        return type("Response", (), {"data": []})()

    @property
    def storage(self):
        return self

    def from_(self, bucket):
        return self

    def remove(self, paths):
        self.removed_paths.extend(paths)
        return {"data": paths}


class _FakeDocRepoForDelete:
    def __init__(self, doc):
        self.doc = doc
        self.client = _FakeDeleteClient()

    def get_by_id(self, doc_id):
        return self.doc if self.doc and self.doc.get("id") == doc_id else None


def test_delete_document_removes_row_and_storage_file():
    doc = {"id": "doc-1", "case_id": "case-1", "file_path": "cases/case-1/test.pdf"}
    doc_repo = _FakeDocRepoForDelete(doc)
    case_repo = FakeCaseRepo({"id": "case-1", "created_by": "reviewer-1"})
    service = DocumentService(doc_repo, case_repo)

    service.delete_document("doc-1", {"id": "reviewer-1", "role": "Reviewer"})

    assert doc_repo.client.removed_paths == ["cases/case-1/test.pdf"]
    assert ("extractions", {"document_id": "doc-1"}) in doc_repo.client.deleted
    assert ("documents", {"id": "doc-1"}) in doc_repo.client.deleted


def test_delete_document_raises_for_unknown_document():
    doc_repo = _FakeDocRepoForDelete(None)
    case_repo = FakeCaseRepo()
    service = DocumentService(doc_repo, case_repo)

    with pytest.raises(ResourceNotFoundError):
        service.delete_document("missing-doc", {"id": "reviewer-1", "role": "Reviewer"})


def test_delete_document_blocks_unrelated_reviewer():
    doc = {"id": "doc-1", "case_id": "case-1", "file_path": "cases/case-1/test.pdf"}
    doc_repo = _FakeDocRepoForDelete(doc)
    case_repo = FakeCaseRepo({"id": "case-1", "created_by": "reviewer-1"})
    service = DocumentService(doc_repo, case_repo)

    with pytest.raises(PermissionDeniedError):
        service.delete_document("doc-1", {"id": "someone-else", "role": "Reviewer"})

    # Nothing should have been deleted once authorization failed.
    assert doc_repo.client.deleted == []
    assert doc_repo.client.removed_paths == []


def test_execute_batch_runs_pipeline_for_every_document(monkeypatch):
    case_repo = FakeCaseRepo()
    doc_repo = FakeDocRepo()
    flag_repo = FakeFlagRepo()
    service = PipelineService(doc_repo, case_repo, flag_repo, FakeDocumentPageRepo())

    processed = []

    def fake_execute(doc_id):
        processed.append(doc_id)
        return {"status": "success", "document_id": doc_id}

    monkeypatch.setattr(service, "execute_analysis_pipeline", fake_execute)

    asyncio.run(service.execute_batch(["doc-1", "doc-2", "doc-3"]))

    assert sorted(processed) == ["doc-1", "doc-2", "doc-3"]


def test_execute_batch_does_not_let_one_failure_stop_the_others(monkeypatch):
    case_repo = FakeCaseRepo()
    doc_repo = FakeDocRepo()
    flag_repo = FakeFlagRepo()
    service = PipelineService(doc_repo, case_repo, flag_repo, FakeDocumentPageRepo())

    processed = []

    def fake_execute(doc_id):
        if doc_id == "doc-2":
            raise RuntimeError("boom")
        processed.append(doc_id)
        return {"status": "success", "document_id": doc_id}

    monkeypatch.setattr(service, "execute_analysis_pipeline", fake_execute)

    asyncio.run(service.execute_batch(["doc-1", "doc-2", "doc-3"]))

    assert sorted(processed) == ["doc-1", "doc-3"]


def test_execute_batch_flags_a_document_whose_pipeline_crashes(monkeypatch, caplog):
    # A document whose execute_analysis_pipeline call raises something it
    # doesn't itself catch (unlike rasterization/extraction failures, which
    # return {"status": "failed", ...} instead of raising) used to be
    # silently swallowed by asyncio.gather(..., return_exceptions=True) —
    # the document just stayed "processing" forever with no error anywhere.
    # It should instead be logged and moved to "flagged" so it's visibly
    # done (if wrongly), not stuck.
    doc_repo = FakeDocRepo({"id": "doc-1", "case_id": "case-1", "file_path": "x", "status": "processing"})
    case_repo = FakeCaseRepo()
    flag_repo = FakeFlagRepo()
    service = PipelineService(doc_repo, case_repo, flag_repo, FakeDocumentPageRepo())

    def fake_execute(doc_id):
        raise RuntimeError("unexpected DB error")

    monkeypatch.setattr(service, "execute_analysis_pipeline", fake_execute)

    with caplog.at_level("ERROR"):
        asyncio.run(service.execute_batch(["doc-1"]))

    assert ("doc-1", "flagged") in doc_repo.updated_statuses
    assert any("pipeline.document_crashed" in record.message for record in caplog.records)


def _patch_routed_pipeline(monkeypatch, *, page_texts=None, has_handwriting=False, extracted_overrides=None):
    """Shared mock setup for the routed OCR/VLM pipeline (Phase 2): stubs
    rasterization, per-page routing, structured text extraction, and
    translation so tests don't need real images or live Gemini/Tesseract calls."""
    page_texts = page_texts or ["transcribed page text"]

    monkeypatch.setattr(
        "app.services.pipeline_service.download_and_rasterize",
        lambda file_url, mime_type: [f"page-{i}-bytes".encode() for i in range(len(page_texts))],
    )
    monkeypatch.setattr(
        "app.services.pipeline_service.enhance_page_image_with_report",
        lambda img: (img, {"fallback": False, "sharpness": 0, "contrast": 0, "noise_sigma": 0, "skew_angle": 0}),
    )
    monkeypatch.setattr(
        "app.services.pipeline_service.route_and_extract_page",
        lambda img, page_number, also_extract_fields=False: {
            "page_number": page_number,
            "original_text": page_texts[page_number - 1],
            "source": "vlm",
            "confidence": None,
            "has_handwriting": has_handwriting,
            "issues": [],
            # None regardless of also_extract_fields — these tests exercise
            # the separate extract_structured_fields_from_text mock below,
            # not the combined-call path (that's covered in
            # test_document_router.py / a dedicated pipeline test instead).
            "structured_fields": None,
        },
    )
    monkeypatch.setattr(
        "app.services.pipeline_service.extract_structured_fields_from_text",
        lambda text: {
            "success": True,
            "raw_output": "structured json",
            "extracted": {"chain": [], **(extracted_overrides or {})},
            "model_used": "demo-model",
            "error": None,
        },
    )

def test_pipeline_skips_separate_extraction_call_for_single_page_combined_result(monkeypatch):
    # When route_and_extract_page's combined call (also_extract_fields=True,
    # single-page documents only) already returned structured fields, the
    # separate extract_structured_fields_from_text call should be skipped
    # entirely rather than redundantly re-extracting from text we already
    # have fields for.
    doc_repo = FakeDocRepo({"id": "doc-1", "case_id": "case-1", "file_path": "cases/case-1/test.pdf", "status": "processing"})
    case_repo = FakeCaseRepo({"id": "case-1", "created_by": "reviewer-1"})
    flag_repo = FakeFlagRepo()
    service = PipelineService(doc_repo, case_repo, flag_repo, FakeDocumentPageRepo())

    monkeypatch.setattr(
        "app.services.pipeline_service.download_and_rasterize",
        lambda file_url, mime_type: [b"page-1-bytes"],
    )
    monkeypatch.setattr(
        "app.services.pipeline_service.enhance_page_image_with_report",
        lambda img: (img, {"fallback": False, "sharpness": 0, "contrast": 0, "noise_sigma": 0, "skew_angle": 0}),
    )
    monkeypatch.setattr(
        "app.services.pipeline_service.route_and_extract_page",
        lambda img, page_number, also_extract_fields=False: {
            "page_number": page_number,
            "original_text": "combined transcription",
            "source": "vlm",
            "confidence": None,
            "has_handwriting": True,
            "issues": [],
            "structured_fields": {"chain": [], "overall_confidence": "high", "owner_name": "Combined Owner"}
            if also_extract_fields else None,
        },
    )
    monkeypatch.setattr(
        "app.services.pipeline_service.extract_structured_fields_from_text",
        lambda text: (_ for _ in ()).throw(AssertionError("separate extraction call should have been skipped")),
    )

    result = service.execute_analysis_pipeline("doc-1")

    assert result["status"] == "success"
    assert result["extracted"]["owner_name"] == "Combined Owner"
    extraction_payload = doc_repo._inserted[-1]
    assert extraction_payload["raw_ocr_text"] == "--- Page 1 ---\ncombined transcription"


def test_pipeline_marks_document_flagged_regardless_of_confidence(monkeypatch):
    # Phase 0: every document is flagged for human review now, not just
    # low-confidence/handwritten ones — this is a high-confidence, no-handwriting
    # extraction and should still land on "flagged".
    doc_repo = FakeDocRepo({"id": "doc-1", "case_id": "case-1", "file_path": "cases/case-1/test.pdf", "status": "processing"})
    case_repo = FakeCaseRepo({"id": "case-1", "created_by": "reviewer-1"})
    flag_repo = FakeFlagRepo()
    service = PipelineService(doc_repo, case_repo, flag_repo, FakeDocumentPageRepo())

    _patch_routed_pipeline(monkeypatch, has_handwriting=False, extracted_overrides={"overall_confidence": "high"})

    result = service.execute_analysis_pipeline("doc-1")

    assert result["status"] == "success"
    assert doc_repo.doc["status"] == "flagged"


def test_pipeline_propagates_handwriting_flag_from_routing(monkeypatch):
    # has_handwritten_content on the extraction record now comes from the
    # router's per-page OCR analysis (document_router.py), not the LLM
    # guessing it from already-transcribed text — see llm_extractor.py's
    # extract_structured_fields_from_text docstring for why.
    doc_repo = FakeDocRepo({"id": "doc-1", "case_id": "case-1", "file_path": "cases/case-1/test.pdf", "status": "processing"})
    case_repo = FakeCaseRepo({"id": "case-1", "created_by": "reviewer-1"})
    flag_repo = FakeFlagRepo()
    service = PipelineService(doc_repo, case_repo, flag_repo, FakeDocumentPageRepo())

    _patch_routed_pipeline(monkeypatch, has_handwriting=True)

    service.execute_analysis_pipeline("doc-1")

    extraction_payload = doc_repo._inserted[-1]
    assert extraction_payload["has_handwritten_content"] is True
    assert extraction_payload["validated_json_output"]["has_handwritten_content"] is True


def test_pipeline_writes_database_confidence_column(monkeypatch):
    doc_repo = FakeDocRepo({
        "id": "doc-1",
        "case_id": "case-1",
        "file_path": "cases/case-1/test.pdf",
        "status": "processing",
    })
    case_repo = FakeCaseRepo({"id": "case-1", "created_by": "reviewer-1"})
    flag_repo = FakeFlagRepo()
    service = PipelineService(doc_repo, case_repo, flag_repo, FakeDocumentPageRepo())

    _patch_routed_pipeline(monkeypatch, has_handwriting=False, extracted_overrides={"overall_confidence": "high"})

    service.execute_analysis_pipeline("doc-1")

    extraction_payload = doc_repo._inserted[-1]
    assert extraction_payload["confidence"] == "high"
    assert "confidence_score" not in extraction_payload


def test_pipeline_merges_routed_pages_into_full_text(monkeypatch):
    doc_repo = FakeDocRepo({"id": "doc-1", "case_id": "case-1", "file_path": "cases/case-1/test.pdf", "status": "processing"})
    case_repo = FakeCaseRepo({"id": "case-1", "created_by": "reviewer-1"})
    flag_repo = FakeFlagRepo()
    doc_page_repo = FakeDocumentPageRepo()
    service = PipelineService(doc_repo, case_repo, flag_repo, doc_page_repo)

    _patch_routed_pipeline(monkeypatch, page_texts=["first page text", "second page text"])

    result = service.execute_analysis_pipeline("doc-1")

    assert "first page text" in result["extracted"]["full_text"]
    assert "second page text" in result["extracted"]["full_text"]
    assert [p["page_number"] for p in doc_page_repo.created_pages] == [1, 2]
    assert [p["original_text"] for p in doc_page_repo.created_pages] == ["first page text", "second page text"]


def test_pipeline_uploads_enhanced_image_per_page(monkeypatch):
    # Enhanced images (post-OpenCV, what OCR/Gemini actually read) are
    # persisted so an Admin can inspect them later — see
    # doc_service.enhanced_page_image_path and the Admin-only
    # GET /documents/{id}/pages/{page_number}/enhanced-image route.
    doc_repo = FakeDocRepo({"id": "doc-1", "case_id": "case-1", "file_path": "cases/case-1/test.pdf", "status": "processing"})
    case_repo = FakeCaseRepo({"id": "case-1", "created_by": "reviewer-1"})
    flag_repo = FakeFlagRepo()
    service = PipelineService(doc_repo, case_repo, flag_repo, FakeDocumentPageRepo())

    _patch_routed_pipeline(monkeypatch, page_texts=["first page text", "second page text"])

    service.execute_analysis_pipeline("doc-1")

    assert [path for path, _, _ in doc_repo.uploaded] == [
        "cases/case-1/enhanced/doc-1/page_1.png",
        "cases/case-1/enhanced/doc-1/page_2.png",
    ]
    assert all(opts == {"content-type": "image/png", "x-upsert": "true"} for _, _, opts in doc_repo.uploaded)


def test_pipeline_survives_enhanced_image_upload_failure(monkeypatch):
    # A storage hiccup while saving the enhanced image shouldn't block
    # extraction itself — same defensive pattern as the document_pages and
    # ownership_chain inserts elsewhere in this pipeline.
    doc_repo = FakeDocRepo({"id": "doc-1", "case_id": "case-1", "file_path": "cases/case-1/test.pdf", "status": "processing"})
    case_repo = FakeCaseRepo({"id": "case-1", "created_by": "reviewer-1"})
    flag_repo = FakeFlagRepo()
    service = PipelineService(doc_repo, case_repo, flag_repo, FakeDocumentPageRepo())

    _patch_routed_pipeline(monkeypatch)

    def _raise_upload(path, file, file_options=None):
        raise RuntimeError("storage unavailable")

    doc_repo._upload = _raise_upload

    result = service.execute_analysis_pipeline("doc-1")

    assert result["status"] == "success"


def test_pipeline_keeps_document_flagged_when_rasterization_fails(monkeypatch):
    doc_repo = FakeDocRepo({"id": "doc-1", "case_id": "case-1", "file_path": "cases/case-1/test.pdf", "status": "processing"})
    case_repo = FakeCaseRepo({"id": "case-1", "created_by": "reviewer-1"})
    flag_repo = FakeFlagRepo()
    service = PipelineService(doc_repo, case_repo, flag_repo, FakeDocumentPageRepo())

    def _raise(file_url, mime_type):
        raise RuntimeError("network unreachable")

    monkeypatch.setattr("app.services.pipeline_service.download_and_rasterize", _raise)

    result = service.execute_analysis_pipeline("doc-1")

    assert result["status"] == "failed"
    assert doc_repo.doc["status"] == "flagged"


def test_pipeline_keeps_document_processing_when_extraction_fails(monkeypatch):
    doc_repo = FakeDocRepo({"id": "doc-1", "case_id": "case-1", "file_path": "cases/case-1/test.pdf", "status": "processing"})
    case_repo = FakeCaseRepo({"id": "case-1", "created_by": "reviewer-1"})
    flag_repo = FakeFlagRepo()
    service = PipelineService(doc_repo, case_repo, flag_repo, FakeDocumentPageRepo())

    monkeypatch.setattr(
        "app.services.pipeline_service.download_and_rasterize",
        lambda file_url, mime_type: [b"page-bytes"],
    )
    monkeypatch.setattr(
        "app.services.pipeline_service.enhance_page_image_with_report",
        lambda img: (img, {"fallback": False, "sharpness": 0, "contrast": 0, "noise_sigma": 0, "skew_angle": 0}),
    )
    monkeypatch.setattr(
        "app.services.pipeline_service.route_and_extract_page",
        lambda img, page_number, also_extract_fields=False: {
            "page_number": page_number, "original_text": "text", "source": "vlm",
            "confidence": None, "has_handwriting": False, "issues": [],
            "structured_fields": None,
        },
    )
    monkeypatch.setattr(
        "app.services.pipeline_service.extract_structured_fields_from_text",
        lambda text: {
            "success": False,
            "raw_output": None,
            "extracted": None,
            "model_used": "demo-model",
            "error": "LLM unavailable",
        },
    )

    result = service.execute_analysis_pipeline("doc-1")

    assert result["status"] == "failed"
    assert doc_repo.doc["status"] == "flagged"


def test_finalize_review_marks_documents_completed():
    case_repo = FakeCaseRepo({"id": "case-1", "created_by": "reviewer-1", "status": "review"})
    flag_repo = FakeFlagRepo()
    doc_repo = FakeDocumentRepoForReview({
        "id": "doc-1",
        "case_id": "case-1",
        "file_path": "cases/case-1/test.pdf",
        "status": "processing",
    })
    service = ReviewService(case_repo, flag_repo, doc_repo)

    result = service.finalize_review("case-1", "approve")

    assert result["status"] == "completed"
    assert doc_repo.doc["status"] == "completed"


def test_assign_reviewer_moves_processed_documents_under_review():
    case_repo = FakeCaseRepo({"id": "case-1", "created_by": "reviewer-1"})
    doc_repo = FakeDocRepo({
        "id": "doc-1",
        "case_id": "case-1",
        "file_path": "cases/case-1/test.pdf",
        "status": "flagged",
    })
    service = ReviewService(case_repo, FakeFlagRepo(), doc_repo)

    result = service.assign_reviewer("case-1", "reviewer-1")

    assert result["reviewer_id"] == "reviewer-1"
    assert case_repo.case_obj["status"] == "review"
    assert doc_repo.doc["status"] == "under_review"


def test_reviewer_submission_persists_edits_notes_and_rejection():
    case_repo = FakeCaseRepo()
    doc_repo = FakeDocRepo({
        "id": "doc-1",
        "case_id": "case-1",
        "file_path": "cases/case-1/test.pdf",
        "status": "under_review",
    })
    extraction_repo = FakeExtractionRepo()
    service = ReviewService(
        case_repo,
        FakeFlagRepo(),
        doc_repo,
        extraction_repo,
    )

    result = service.submit_document_review(
        "doc-1",
        "reviewer-1",
        {"survey_number": "SY-CORRECTED"},
        "Survey number needs verification.",
        "rejected",
    )

    assert result["document"]["status"] == "rejected"
    assert result["extraction"]["validated_json_output"] == {"survey_number": "SY-CORRECTED"}
    assert result["extraction"]["review_notes"] == "Survey number needs verification."
    assert result["extraction"]["status"] == "rejected"


def test_reviewer_can_save_field_edits_without_deciding():
    # decision omitted entirely — reviewer is saving corrections as they go,
    # not finalizing approve/reject in the same action.
    case_repo = FakeCaseRepo()
    doc_repo = FakeDocRepo({
        "id": "doc-1",
        "case_id": "case-1",
        "file_path": "cases/case-1/test.pdf",
        "status": "flagged",
    })
    extraction_repo = FakeExtractionRepo()
    service = ReviewService(case_repo, FakeFlagRepo(), doc_repo, extraction_repo)

    result = service.submit_document_review(
        "doc-1",
        "reviewer-1",
        {"survey_number": "SY-CORRECTED"},
        "Just fixing a typo, not done reviewing yet.",
    )

    # Edits persisted...
    assert result["extraction"]["validated_json_output"] == {"survey_number": "SY-CORRECTED"}
    assert result["extraction"]["review_notes"] == "Just fixing a typo, not done reviewing yet."
    # ...but nothing about the document/extraction's review status changed.
    assert result["document"]["status"] == "flagged"
    assert "status" not in extraction_repo.updated[-1][2]
    assert "reviewed_by" not in extraction_repo.updated[-1][2]


def test_reviewer_submission_rejects_invalid_decision_value():
    case_repo = FakeCaseRepo()
    doc_repo = FakeDocRepo({"id": "doc-1", "case_id": "case-1", "file_path": "cases/case-1/test.pdf", "status": "flagged"})
    extraction_repo = FakeExtractionRepo()
    service = ReviewService(case_repo, FakeFlagRepo(), doc_repo, extraction_repo)

    with pytest.raises(Exception):
        service.submit_document_review("doc-1", "reviewer-1", {}, None, "maybe")
