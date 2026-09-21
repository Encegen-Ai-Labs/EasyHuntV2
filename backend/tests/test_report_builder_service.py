import pytest

from app.core.exceptions import PermissionDeniedError, PropertySystemException, ResourceNotFoundError
from app.services.doc_service import DocumentService
from app.services.report_builder_service import ReportBuilderService

CASE_ID = "case-1"
DOC_ID = "doc-1"


class FakeCaseRepo:
    def __init__(self, case_obj=None):
        self.case_obj = case_obj or {"id": CASE_ID, "created_by": "reviewer-1"}

    def get_by_id(self, case_id):
        return self.case_obj if self.case_obj.get("id") == case_id else None


class FakeDocRepo:
    def __init__(self, docs=None):
        self.docs = docs if docs is not None else [
            {"id": DOC_ID, "case_id": CASE_ID, "file_name": "sale_deed.pdf"}
        ]

    def get_by_id(self, doc_id):
        return next((d for d in self.docs if d["id"] == doc_id), None)

    def list_by_case(self, case_id):
        return [d for d in self.docs if d.get("case_id") == case_id]


class FakeStorageBucket:
    def __init__(self):
        self.uploaded = []  # list of (path, bytes)

    def upload(self, path, file, file_options=None):
        self.uploaded.append((path, file))
        return {"path": path}

    def create_signed_url(self, path, expires_in):
        return {"signedURL": f"https://example.com/{path}?signed=true"}


class FakeStorage:
    def __init__(self):
        self.bucket = FakeStorageBucket()

    def from_(self, bucket_name):
        return self.bucket


class FakeSupabaseClient:
    def __init__(self):
        self.storage = FakeStorage()


class FakeReportRepo:
    def __init__(self):
        self.reports = {}
        self.created = []
        self._next_id = 1
        self.client = FakeSupabaseClient()

    def get_by_case_and_type(self, case_id, report_type):
        return self.reports.get((case_id, report_type))

    def create_report(self, report_data):
        report = {**report_data, "id": f"report-{self._next_id}"}
        self._next_id += 1
        self.reports[(report_data["case_id"], report_data["report_type"])] = report
        self.created.append(report)
        return report

    def update_file_path(self, report_id, file_path):
        for report in self.reports.values():
            if report["id"] == report_id:
                report["file_path"] = file_path
                return report
        return None


class FakeExcerptRepo:
    def __init__(self):
        self.excerpts = {}
        self._next_id = 1

    def list_by_report(self, report_id):
        rows = [e for e in self.excerpts.values() if e["report_id"] == report_id]
        return sorted(rows, key=lambda r: r["sequence_order"])

    def create(self, excerpt_data):
        excerpt = {**excerpt_data, "id": f"excerpt-{self._next_id}"}
        self._next_id += 1
        self.excerpts[excerpt["id"]] = excerpt
        return excerpt

    def get_by_id(self, excerpt_id):
        return self.excerpts.get(excerpt_id)

    def delete_excerpt(self, excerpt_id):
        self.excerpts.pop(excerpt_id, None)

    def update_note(self, excerpt_id, note):
        if excerpt_id in self.excerpts:
            self.excerpts[excerpt_id]["note"] = note
        return self.excerpts.get(excerpt_id)

    def update_fields(self, excerpt_id, fields):
        if excerpt_id in self.excerpts:
            self.excerpts[excerpt_id].update(fields)
        return self.excerpts.get(excerpt_id)

    def update_sequence(self, excerpt_id, sequence_order):
        if excerpt_id in self.excerpts:
            self.excerpts[excerpt_id]["sequence_order"] = sequence_order


def make_service(case_repo=None, doc_repo=None, report_repo=None, excerpt_repo=None):
    case_repo = case_repo or FakeCaseRepo()
    doc_repo = doc_repo or FakeDocRepo()
    doc_service = DocumentService(doc_repo, case_repo)
    return ReportBuilderService(
        doc_service, report_repo or FakeReportRepo(), excerpt_repo or FakeExcerptRepo(), doc_repo
    )


REVIEWER = {"id": "reviewer-1", "role": "Reviewer"}


def test_get_or_create_report_creates_exactly_one_report_per_case():
    report_repo = FakeReportRepo()
    service = make_service(report_repo=report_repo)

    first = service.get_or_create_report(CASE_ID, REVIEWER)
    second = service.get_or_create_report(CASE_ID, REVIEWER)

    assert first["id"] == second["id"]
    assert len(report_repo.created) == 1
    assert first["report_type"] == "manual"
    assert first["status"] == "draft"


def test_add_excerpt_assigns_sequential_order():
    service = make_service()

    first = service.add_excerpt(CASE_ID, DOC_ID, 1, "first excerpt", None, REVIEWER)
    second = service.add_excerpt(CASE_ID, DOC_ID, 2, "second excerpt", None, REVIEWER)

    assert first["sequence_order"] == 0
    assert second["sequence_order"] == 1


def test_add_excerpt_rejects_document_from_a_different_case():
    doc_repo = FakeDocRepo(docs=[{"id": DOC_ID, "case_id": "some-other-case", "file_name": "deed.pdf"}])
    service = make_service(doc_repo=doc_repo)

    with pytest.raises(ResourceNotFoundError):
        service.add_excerpt(CASE_ID, DOC_ID, 1, "text", None, REVIEWER)


def test_get_report_with_excerpts_denormalizes_document_name():
    service = make_service()
    service.add_excerpt(CASE_ID, DOC_ID, 3, "some excerpt", "a note", REVIEWER)

    result = service.get_report_with_excerpts(CASE_ID, REVIEWER)

    assert len(result["excerpts"]) == 1
    assert result["excerpts"][0]["document_name"] == "sale_deed.pdf"
    assert result["excerpts"][0]["note"] == "a note"


def test_remove_excerpt_deletes_it():
    excerpt_repo = FakeExcerptRepo()
    service = make_service(excerpt_repo=excerpt_repo)
    excerpt = service.add_excerpt(CASE_ID, DOC_ID, 1, "text", None, REVIEWER)

    service.remove_excerpt(CASE_ID, excerpt["id"], REVIEWER)

    assert excerpt_repo.get_by_id(excerpt["id"]) is None


def test_remove_excerpt_from_another_report_is_rejected():
    service = make_service()

    with pytest.raises(ResourceNotFoundError):
        service.remove_excerpt(CASE_ID, "nonexistent-excerpt", REVIEWER)


def test_update_excerpt_note_updates_only_the_note():
    service = make_service()
    excerpt = service.add_excerpt(CASE_ID, DOC_ID, 1, "text", None, REVIEWER)

    updated = service.update_excerpt_note(CASE_ID, excerpt["id"], "now with a note", REVIEWER)

    assert updated["note"] == "now with a note"
    assert updated["excerpt_text"] == "text"


def test_update_excerpt_note_can_also_edit_excerpt_text():
    # A reviewer correcting the cited wording itself (e.g. an OCR/VLM slip),
    # not just annotating it — both save in the same call.
    service = make_service()
    excerpt = service.add_excerpt(CASE_ID, DOC_ID, 1, "orignal typo", None, REVIEWER)

    updated = service.update_excerpt_note(
        CASE_ID, excerpt["id"], "fixed a typo", REVIEWER, excerpt_text="original, corrected"
    )

    assert updated["note"] == "fixed a typo"
    assert updated["excerpt_text"] == "original, corrected"


def test_update_excerpt_note_without_excerpt_text_leaves_it_unchanged():
    service = make_service()
    excerpt = service.add_excerpt(CASE_ID, DOC_ID, 1, "unchanged text", None, REVIEWER)

    updated = service.update_excerpt_note(CASE_ID, excerpt["id"], "just a note", REVIEWER)

    assert updated["excerpt_text"] == "unchanged text"


def test_reorder_excerpts_updates_sequence_order():
    service = make_service()
    first = service.add_excerpt(CASE_ID, DOC_ID, 1, "first", None, REVIEWER)
    second = service.add_excerpt(CASE_ID, DOC_ID, 2, "second", None, REVIEWER)

    reordered = service.reorder_excerpts(CASE_ID, [second["id"], first["id"]], REVIEWER)

    assert [e["id"] for e in reordered] == [second["id"], first["id"]]
    assert reordered[0]["sequence_order"] == 0
    assert reordered[1]["sequence_order"] == 1


def test_reorder_excerpts_rejects_mismatched_id_list():
    service = make_service()
    service.add_excerpt(CASE_ID, DOC_ID, 1, "first", None, REVIEWER)

    with pytest.raises(PropertySystemException):
        service.reorder_excerpts(CASE_ID, ["not-a-real-excerpt-id"], REVIEWER)


def test_unrelated_reviewer_is_blocked_from_the_case_report():
    case_repo = FakeCaseRepo({"id": CASE_ID, "created_by": "someone-else"})
    service = make_service(case_repo=case_repo)

    with pytest.raises(PermissionDeniedError):
        service.get_or_create_report(CASE_ID, REVIEWER)


def test_export_pdf_uploads_updates_file_path_and_returns_signed_url():
    report_repo = FakeReportRepo()
    service = make_service(report_repo=report_repo)
    service.add_excerpt(CASE_ID, DOC_ID, 1, "the excerpt text", None, REVIEWER)

    result = service.export_pdf(CASE_ID, REVIEWER)

    assert result["file_path"] == f"reports/{CASE_ID}/manual/report.pdf"
    assert result["download_url"] == f"https://example.com/reports/{CASE_ID}/manual/report.pdf?signed=true"

    # Uploaded bytes are a real PDF, not a placeholder.
    uploaded_path, uploaded_bytes = report_repo.client.storage.bucket.uploaded[-1]
    assert uploaded_path == result["file_path"]
    assert uploaded_bytes.startswith(b"%PDF")

    # The report row was updated with the same path.
    report = report_repo.get_by_case_and_type(CASE_ID, "manual")
    assert report["file_path"] == result["file_path"]


def test_export_pdf_is_idempotent_and_reuses_the_same_report_row():
    report_repo = FakeReportRepo()
    service = make_service(report_repo=report_repo)
    service.add_excerpt(CASE_ID, DOC_ID, 1, "excerpt", None, REVIEWER)

    service.export_pdf(CASE_ID, REVIEWER)
    service.export_pdf(CASE_ID, REVIEWER)

    assert len(report_repo.created) == 1
    assert len(report_repo.client.storage.bucket.uploaded) == 2


def test_export_pdf_translates_every_excerpt_and_embeds_it_in_the_pdf(monkeypatch):
    # User's explicit choice (2026-08-21): every excerpt always shows both
    # languages in the exported PDF, translated fresh at export time rather
    # than reusing whatever page-level translation may or may not exist.
    report_repo = FakeReportRepo()
    service = make_service(report_repo=report_repo)
    service.add_excerpt(CASE_ID, DOC_ID, 1, "दिनांक विषयी वाक्य", None, REVIEWER)

    translate_calls = []

    def fake_translate(text):
        translate_calls.append(text)
        return {"success": True, "translated_text": "A sentence about the date", "error": None}

    monkeypatch.setattr("app.services.report_builder_service.translate_to_english", fake_translate)

    result = service.export_pdf(CASE_ID, REVIEWER)

    assert translate_calls == ["दिनांक विषयी वाक्य"]
    uploaded_path, uploaded_bytes = report_repo.client.storage.bucket.uploaded[-1]
    assert uploaded_path == result["file_path"]
    assert b"NotoSansDevanagari" in uploaded_bytes  # confirms the English line rendered too, not just excerpt_text


def test_export_pdf_survives_a_failed_translation():
    # A Translate API hiccup on one excerpt shouldn't block the whole export
    # — same fallback-sentinel pattern as translation_service.translate_pages().
    report_repo = FakeReportRepo()
    service = make_service(report_repo=report_repo)
    service.add_excerpt(CASE_ID, DOC_ID, 1, "excerpt with no translate key configured", None, REVIEWER)

    # No GOOGLE_TRANSLATE_API_KEY in the test environment, so the real
    # translate_to_english() call fails gracefully rather than being mocked —
    # deliberately exercising the real failure path, not a stubbed one.
    result = service.export_pdf(CASE_ID, REVIEWER)

    assert result["file_path"] == f"reports/{CASE_ID}/manual/report.pdf"
    uploaded_path, uploaded_bytes = report_repo.client.storage.bucket.uploaded[-1]
    assert uploaded_bytes.startswith(b"%PDF")
