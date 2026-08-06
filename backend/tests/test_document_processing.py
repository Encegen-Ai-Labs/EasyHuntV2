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

    def update(self, data):
        return self

    def execute(self):
        return type("Response", (), {"data": [self._inserted[-1]]})()
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

    assert result["status"] == "flagged"
    assert doc_repo.doc["status"] == "flagged"


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

    assert result["status"] == "processing"
    assert doc_repo.doc["status"] == "processing"


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
