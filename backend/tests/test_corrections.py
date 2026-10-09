"""Corrections dataset: diffing, recording, the review-save integration, and
export into the evaluation-set format."""
import json
from pathlib import Path

import pytest

from app.core.exceptions import PropertySystemException
from app.services import corrections_service as cs
from app.services.corrections_service import CorrectionRecorder, confirm_rows, diff_extraction
from app.services.review_service import ReviewService

from eval import export_corrections as ex
from eval import loader

from test_document_processing import FakeCaseRepo, FakeDocRepo, FakeFlagRepo


def paths(rows):
    return {r["field_path"]: r for r in rows}


# --------------------------------------------------------------------- diff

def test_edit_add_clear_and_original_value():
    original = {"owner_name": "Ramesh Patel", "area": None, "survey_number": "45/2B"}
    before = {"owner_name": "Ramesh Patel", "area": None, "survey_number": "45/2B"}
    after = {"owner_name": "Ramesh Patil", "area": "2 acre", "survey_number": ""}
    rows = paths(diff_extraction(original, before, after))
    assert rows["owner_name"]["change_type"] == cs.EDIT and rows["owner_name"]["original_value"] == "Ramesh Patel"
    assert rows["area"]["change_type"] == cs.ADD
    assert rows["survey_number"]["change_type"] == cs.CLEAR
    assert rows["survey_number"]["previous_value"] == "45/2B" and rows["survey_number"]["corrected_value"] == ""


def test_repeated_edit_keeps_model_original_and_previous_value():
    original = {"owner_name": "Model Guess"}
    rows = diff_extraction(original, {"owner_name": "First Edit"}, {"owner_name": "Second Edit"})
    assert rows[0]["original_value"] == "Model Guess"
    assert rows[0]["previous_value"] == "First Edit" and rows[0]["corrected_value"] == "Second Edit"


def test_untouched_values_do_not_count_even_when_form_stringified_them():
    before = {"has_handwritten_content": True, "owner_name": "A", "full_text": "x", "owner_name_confidence": "high"}
    after = {"has_handwritten_content": "true", "owner_name": " A ", "full_text": "changed", "owner_name_confidence": "low"}
    assert diff_extraction({}, before, after) == []


def test_chain_changes_are_per_link_and_per_key():
    before = {"chain": [{"order": 1, "owner": "A", "date": "1990-01-01"}, {"order": 2, "owner": "B", "date": "1999-01-01"}]}
    after = {"chain": [{"order": 1, "owner": "A", "date": "1991-01-01"}]}
    rows = paths(diff_extraction(before, before, after))
    assert rows["chain[0].date"]["change_type"] == cs.EDIT and rows["chain[0].date"]["corrected_value"] == "1991-01-01"
    assert rows["chain[1]"]["change_type"] == cs.REMOVE
    added = paths(diff_extraction({}, {"chain": []}, {"chain": [{"order": 1, "owner": "A"}]}))
    assert added["chain[0]"]["change_type"] == cs.ADD


def test_confirm_rows_only_for_untouched_fields():
    before = after = {"owner_name": "A", "survey_number": "1", "chain": [], "red_flags": []}
    changed = diff_extraction({}, before, {**after, "owner_name": "B"})
    conf = confirm_rows({}, before, {**after, "owner_name": "B"}, changed)
    assert {r["field_path"] for r in conf} == {"survey_number", "chain", "red_flags"}
    assert all(r["change_type"] == cs.CONFIRM for r in conf)


# ---------------------------------------------------------------- recording

class MemRepo:
    def __init__(self, existing=None, fail=False):
        self.rows = list(existing or [])
        self.fail = fail

    def select(self, table, filters=None, order_by=None):
        if self.fail:
            raise RuntimeError("relation extraction_corrections does not exist")
        return [r for r in self.rows if all(r.get(k) == v for k, v in (filters or {}).items())]

    def bulk_insert(self, table, rows):
        if self.fail:
            raise RuntimeError("relation extraction_corrections does not exist")
        self.rows.extend(rows)
        return rows


EXTRACTION = {"id": "ex-1", "document_id": "doc-1", "model_used": "m", "has_handwritten_content": True,
              "raw_json_output": {"owner_name": "Model Guess", "owner_name_confidence": "medium", "survey_number": "9"},
              "validated_json_output": {"owner_name": "Model Guess", "survey_number": "9"}}
DOCUMENT = {"id": "doc-1", "case_id": "case-1"}


def test_record_review_stamps_context_revision_and_reason():
    repo = MemRepo()
    rec = CorrectionRecorder(repo)
    out = rec.record_review(extraction=EXTRACTION, document=DOCUMENT, reviewer_id="u1",
                            after={"owner_name": "Real Name", "survey_number": "9"}, approved=False,
                            reasons={"owner_name": "misread", "bogus": "x"})
    assert out == {"recorded": True, "count": 1}
    row = repo.rows[0]
    assert (row["revision"], row["corrected_by"], row["case_id"], row["handwriting"]) == (1, "u1", "case-1", True)
    assert row["reason"] == "misread" and row["model_confidence"] == "medium" and row["model_used"] == "m"
    # next save is revision 2; an invalid reason is dropped
    rec.record_review(extraction={**EXTRACTION, "validated_json_output": {"owner_name": "Real Name", "survey_number": "9"}},
                      document=DOCUMENT, reviewer_id="u1", after={"owner_name": "Final", "survey_number": "9"},
                      approved=False, reasons={"owner_name": "not-a-reason"})
    assert repo.rows[1]["revision"] == 2 and repo.rows[1]["reason"] is None


def test_no_change_and_save_without_decision_record_nothing_extra():
    repo = MemRepo()
    rec = CorrectionRecorder(repo)
    out = rec.record_review(extraction=EXTRACTION, document=DOCUMENT, reviewer_id="u", approved=False,
                            after=dict(EXTRACTION["validated_json_output"]))
    assert out == {"recorded": True, "count": 0} and repo.rows == []


def test_approval_records_confirm_rows():
    repo = MemRepo()
    CorrectionRecorder(repo).record_review(
        extraction=EXTRACTION, document=DOCUMENT, reviewer_id="u", approved=True,
        after={"owner_name": "Fixed", "survey_number": "9"})
    kinds = {r["field_path"]: r["change_type"] for r in repo.rows}
    assert kinds == {"owner_name": "edit", "survey_number": "confirm"}


def test_recording_failure_is_reported_not_raised():
    out = CorrectionRecorder(MemRepo(fail=True)).record_review(
        extraction=EXTRACTION, document=DOCUMENT, reviewer_id="u", approved=False,
        after={"owner_name": "X", "survey_number": "9"})
    assert out == {"recorded": False, "count": 0}


def test_page_text_edit_is_recorded_with_previous_text():
    repo = MemRepo()
    rec = CorrectionRecorder(repo)
    assert rec.record_page_text(document=DOCUMENT, extraction_id="ex-1", reviewer_id="u", page_number=3,
                                column="original_text", previous="old text", corrected="new text")
    row = repo.rows[0]
    assert row["field_path"] == "page[3].original_text" and row["previous_value"] == "old text"
    assert rec.record_page_text(document=DOCUMENT, extraction_id="ex-1", reviewer_id="u", page_number=3,
                                column="original_text", previous="same", corrected="same")
    assert len(repo.rows) == 1  # an unchanged text records nothing


# ------------------------------------------------------ review integration

class Extractions:
    def __init__(self, update_returns_rows=True):
        self.row = {**EXTRACTION, "status": "pending_review"}
        self.update_returns_rows = update_returns_rows
        self.order_by_seen = []

    def select_one(self, table, filters, order_by=None):
        self.order_by_seen.append(order_by)
        return self.row

    def update(self, table, filters, payload):
        if not self.update_returns_rows:
            return []
        self.row = {**self.row, **payload}
        return [self.row]


def make_service(extractions, recorder):
    doc_repo = FakeDocRepo({"id": "doc-1", "case_id": "case-1", "file_path": "p", "status": "flagged"})
    return ReviewService(FakeCaseRepo(), FakeFlagRepo(), doc_repo, extractions, recorder), doc_repo


def test_review_save_records_corrections_and_returns_summary():
    repo = MemRepo()
    ext = Extractions()
    service, _ = make_service(ext, CorrectionRecorder(repo))
    result = service.submit_document_review(
        "doc-1", "u1", {"owner_name": "Real Name", "survey_number": "9"}, None, "approved",
        reasons={"owner_name": "hallucinated"})
    assert result["corrections"] == {"recorded": True, "count": 2}
    assert {r["field_path"] for r in repo.rows} == {"owner_name", "survey_number"}
    assert ext.order_by_seen == ["id"]  # deterministic row choice


def test_zero_row_update_is_an_error_and_does_not_change_document_status():
    repo = MemRepo()
    service, doc_repo = make_service(Extractions(update_returns_rows=False), CorrectionRecorder(repo))
    with pytest.raises(PropertySystemException) as e:
        service.submit_document_review("doc-1", "u1", {"owner_name": "X"}, None, "approved")
    assert e.value.status_code == 409
    assert doc_repo.doc["status"] == "flagged" and repo.rows == []


def test_broken_corrections_table_never_blocks_the_save():
    service, _ = make_service(Extractions(), CorrectionRecorder(MemRepo(fail=True)))
    result = service.submit_document_review("doc-1", "u1", {"owner_name": "X", "survey_number": "9"}, None)
    assert result["extraction"]["validated_json_output"]["owner_name"] == "X"
    assert result["corrections"]["recorded"] is False


# ------------------------------------------------------------------- export

APPROVED = {
    "id": "ex-1", "document_id": "doc-1", "status": "approved", "reviewed_at": "2026-10-10T00:00:00Z",
    "has_handwritten_content": False,
    "validated_json_output": {
        "document_type": "sale_deed", "owner_name": "Ramesh Kumar Patil", "previous_owner_name": None,
        "survey_number": "45/2B", "transaction_date": "1998-03-12", "language_detected": "Marathi",
        "property_location": "Wagholi", "full_text": "...",
        "chain": [{"order": 1, "owner": "Ramesh Kumar Patil", "date": "1998-03-12", "type": "Sale Deed", "survey": "45/2B"}],
        "red_flags": [{"type": "encumbrance", "description": "d", "severity": "high", "source_text": "mortgaged"}],
    },
}
CORRECTIONS = [
    {"field_path": "owner_name", "change_type": "edit"},
    {"field_path": "survey_number", "change_type": "confirm"},
    {"field_path": "previous_owner_name", "change_type": "clear"},
    {"field_path": "chain[0].date", "change_type": "edit"},
    {"field_path": "page[1].original_text", "change_type": "edit"},   # page edits never label fields
]


def test_only_human_touched_fields_are_labelled():
    exp = ex.build_expected(APPROVED, CORRECTIONS, "2026-10-12")
    assert set(exp["fields"]) == {"owner_name", "survey_number", "previous_owner_name"}
    assert exp["fields"]["previous_owner_name"] is None            # cleared = the correct answer is null
    assert "transaction_date" in exp["unlabelled"] and "property_location" in exp["unlabelled"]
    assert exp["chain"][0]["date"] == "1998-03-12" and "red_flags" in exp["unlabelled"] and "red_flags" not in exp


def test_eligibility_requires_approval():
    assert ex.eligible(APPROVED)[0]
    assert not ex.eligible({**APPROVED, "status": "rejected"})[0]
    assert not ex.eligible({**APPROVED, "reviewed_at": None})[0]


def test_exported_case_loads_scores_and_is_never_overwritten(tmp_path):
    case_dir = ex.write_case(tmp_path, APPROVED, CORRECTIONS, "cases/c/deed.pdf", b"%PDF", "holdout", 2, "2026-10-12")
    assert case_dir.name == "0001_sale_deed"
    second = ex.write_case(tmp_path, APPROVED, CORRECTIONS, "cases/c/deed.pdf", b"%PDF2", "holdout", 2, "2026-10-12")
    assert second.name == "0002_sale_deed"
    cases = loader.load_cases(tmp_path)               # validates the format strictly
    assert [c.id for c in cases] == ["0001_sale_deed", "0002_sale_deed"]
    assert cases[0].split == "holdout" and cases[0].meta["language"] == "marathi"
    assert (case_dir / "source.pdf").read_bytes() == b"%PDF"


# ------------------------------------------------- page edits and the race

def test_page_edit_helper_records_both_columns_and_survives_failure(monkeypatch):
    from types import SimpleNamespace
    from app.api.v1 import documents as docs

    repo = MemRepo()
    repo.select_one = lambda table, filters, order_by=None: {"id": "ex-1"}
    monkeypatch.setattr(docs, "BaseRepository", lambda client: repo)
    payload = SimpleNamespace(original_text="new orig", english_text=None)
    docs._record_page_corrections(
        SimpleNamespace(doc_repo=SimpleNamespace(client=None)), DOCUMENT, {"id": "u1"}, 2,
        {"original_text": "old orig", "english_text": "old eng"}, payload)
    assert [(r["field_path"], r["previous_value"], r["corrected_value"]) for r in repo.rows] == [
        ("page[2].original_text", "old orig", "new orig")]

    def boom(client):
        raise RuntimeError("db down")
    monkeypatch.setattr(docs, "BaseRepository", boom)
    docs._record_page_corrections(  # must not raise
        SimpleNamespace(doc_repo=SimpleNamespace(client=None)), DOCUMENT, {"id": "u1"}, 2, {}, payload)


def test_pipeline_insert_losing_a_race_is_not_a_failure(monkeypatch):
    from test_extraction_cache import setup_pipeline
    from pathlib import Path
    import tempfile
    service, repo, c, _ = setup_pipeline(monkeypatch, Path(tempfile.mkdtemp()), cache=False)

    def boom(table, data):
        raise RuntimeError("duplicate key value violates unique constraint extractions_document_id_key")
    existing = [{"document_id": "doc-1", "validated_json_output": {"owner_name": "from the winner"}}]
    calls = {"n": 0}

    def fake_select(table, filters=None, order_by=None):
        calls["n"] += 1
        return [] if calls["n"] == 1 else existing   # empty at the start of the run, present after the loss
    service.generic_repo.insert = boom
    service.generic_repo.select = fake_select
    result = service.execute_analysis_pipeline("doc-1")
    assert result["status"] == "already_processed" and result["extracted"] == {"owner_name": "from the winner"}
    assert "flagged" not in [s for _, s in repo.updated_statuses]
