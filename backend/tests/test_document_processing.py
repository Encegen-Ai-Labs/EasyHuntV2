from app.services.doc_service import DocumentService
from app.services.pipeline_service import PipelineService
from app.services.review_service import ReviewService


class FakeCaseRepo:
    def __init__(self, case_obj=None):
        self.case_obj = case_obj or {"id": "case-1", "created_by": "vendor-1"}
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
        current_user={"id": "vendor-1", "role": "Vendor"},
    )

    assert result["status"] == "processing"
    assert result["file_path"] == "cases/case-1/test.pdf"
    assert result["id"] == "doc-1"


def test_pipeline_marks_document_flagged_for_handwriting(monkeypatch):
    doc_repo = FakeDocRepo({"id": "doc-1", "case_id": "case-1", "file_path": "cases/case-1/test.pdf", "status": "processing"})
    case_repo = FakeCaseRepo({"id": "case-1", "created_by": "vendor-1"})
    flag_repo = FakeFlagRepo()
    service = PipelineService(doc_repo, case_repo, flag_repo)

    monkeypatch.setattr("app.services.pipeline_service.extract_from_supabase_url", lambda file_url: {
        "success": True,
        "raw_output": "handwriting detected",
        "extracted": {"confidence": "low", "handwriting_detected": True, "chain": []},
        "model_used": "demo-model",
        "error": None,
    })

    result = service.execute_analysis_pipeline("doc-1")

    assert result["status"] == "success"
    assert doc_repo.doc["status"] == "flagged"


def test_pipeline_writes_database_confidence_column(monkeypatch):
    doc_repo = FakeDocRepo({
        "id": "doc-1",
        "case_id": "case-1",
        "file_path": "cases/case-1/test.pdf",
        "status": "processing",
    })
    case_repo = FakeCaseRepo({"id": "case-1", "created_by": "vendor-1"})
    flag_repo = FakeFlagRepo()
    service = PipelineService(doc_repo, case_repo, flag_repo)

    monkeypatch.setattr("app.services.pipeline_service.extract_from_supabase_url", lambda file_url: {
        "success": True,
        "raw_output": "plain text",
        "extracted": {
            "overall_confidence": "high",
            "has_handwritten_content": False,
            "chain": [],
        },
        "model_used": "demo-model",
        "error": None,
    })

    service.execute_analysis_pipeline("doc-1")

    extraction_payload = doc_repo._inserted[-1]
    assert extraction_payload["confidence"] == "high"
    assert "confidence_score" not in extraction_payload


def test_pipeline_keeps_document_processing_when_extraction_fails(monkeypatch):
    doc_repo = FakeDocRepo({"id": "doc-1", "case_id": "case-1", "file_path": "cases/case-1/test.pdf", "status": "processing"})
    case_repo = FakeCaseRepo({"id": "case-1", "created_by": "vendor-1"})
    flag_repo = FakeFlagRepo()
    service = PipelineService(doc_repo, case_repo, flag_repo)

    monkeypatch.setattr("app.services.pipeline_service.extract_from_supabase_url", lambda file_url: {
        "success": False,
        "raw_output": None,
        "extracted": None,
        "model_used": "demo-model",
        "error": "LLM unavailable",
    })

    result = service.execute_analysis_pipeline("doc-1")

    assert result["status"] == "failed"
    assert doc_repo.doc["status"] == "flagged"


def test_finalize_review_marks_documents_completed():
    case_repo = FakeCaseRepo({"id": "case-1", "created_by": "vendor-1", "status": "review"})
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
    case_repo = FakeCaseRepo({"id": "case-1", "created_by": "vendor-1"})
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
