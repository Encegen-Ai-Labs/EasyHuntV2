import pytest

from app.core.exceptions import PropertySystemException
from app.services.review_service import ReviewService
from app.services.search_service import SearchService, find_similar_terms


def _page(doc="doc-1", number=1, original="", english=""):
    return {"document_id": doc, "page_number": number, "original_text": original, "english_text": english}


# --- similar words ---

def test_exact_word_comes_first_then_close_spellings():
    pages = [
        _page(original="Ramesh Patil sold to Suresh Pateel. Patil Patil. Patilwadi village. Kulkarni."),
    ]

    terms = find_similar_terms(pages, "patil")

    assert [t["term"] for t in terms][0] == "Patil"
    assert terms[0]["kind"] == "exact" and terms[0]["count"] == 3
    similar = {t["term"] for t in terms if t["kind"] == "similar"}
    assert {"Pateel", "Patilwadi"} <= similar
    assert "Kulkarni" not in {t["term"] for t in terms}


def test_devanagari_spelling_variant_is_offered():
    pages = [_page(original="श्री पाटील आणि पाटिल यांनी")]

    terms = find_similar_terms(pages, "पाटील")

    by_term = {t["term"]: t["kind"] for t in terms}
    assert by_term["पाटील"] == "exact"
    assert by_term["पाटिल"] == "similar"


def test_locations_list_each_page_once():
    pages = [_page(number=1, original="Patil Patil"), _page(doc="doc-2", number=4, english="patil")]

    terms = find_similar_terms(pages, "Patil")

    assert terms[0]["count"] == 3
    assert terms[0]["locations"] == [
        {"document_id": "doc-1", "page_number": 1},
        {"document_id": "doc-2", "page_number": 4},
    ]


def test_blank_query_and_short_words_find_nothing_similar():
    assert find_similar_terms([_page(original="a an the")], "   ") == []
    assert [t["kind"] for t in find_similar_terms([_page(original="an and ant")], "an")] == ["exact"]


# --- search only covers approved documents ---

class _CaseRepo:
    def get_by_id(self, case_id):
        return {"id": case_id, "created_by": "u1"}


class _DocRepo:
    def list_by_case(self, case_id):
        return [
            {"id": "approved-doc", "case_id": case_id, "file_name": "a.pdf", "status": "approved"},
            {"id": "pending-doc", "case_id": case_id, "file_name": "b.pdf", "status": "llm_done"},
            {"id": "flagged-doc", "case_id": case_id, "file_name": "c.pdf", "status": "flagged"},
        ]


class _PageRepo:
    def __init__(self):
        self.exact_ids = None
        self.terms_ids = None

    def search_by_case(self, document_ids, query):
        self.exact_ids = document_ids
        return []

    def list_by_documents(self, document_ids):
        self.terms_ids = document_ids
        return [_page(doc=document_ids[0], original="Patil")]


def _search_service(page_repo):
    from app.services.doc_service import DocumentService

    return SearchService(DocumentService(_DocRepo(), _CaseRepo()), _DocRepo(), page_repo)


USER = {"id": "u1", "role": "Reviewer"}


def test_exact_search_covers_only_approved_documents():
    pages = _PageRepo()
    _search_service(pages).search_case("case-1", "Patil", USER)
    assert pages.exact_ids == ["approved-doc"]


def test_term_lookup_covers_only_approved_documents():
    pages = _PageRepo()
    terms = _search_service(pages).find_terms("case-1", "Patil", USER)
    assert pages.terms_ids == ["approved-doc"]
    assert terms[0]["term"] == "Patil"


def test_term_lookup_with_no_approved_documents_returns_nothing():
    class NoneApproved(_DocRepo):
        def list_by_case(self, case_id):
            return [{"id": "x", "case_id": case_id, "status": "llm_done"}]

    from app.services.doc_service import DocumentService

    service = SearchService(DocumentService(NoneApproved(), _CaseRepo()), NoneApproved(), _PageRepo())
    assert service.find_terms("case-1", "Patil", USER) == []


# --- undo an approval ---

class _ReviewDocRepo:
    def __init__(self, status):
        self.doc = {"id": "doc-1", "case_id": "case-1", "status": status}
        self.client = object()

    def get_by_id(self, doc_id):
        return self.doc if doc_id == "doc-1" else None

    def update_status(self, doc_id, status):
        self.doc["status"] = status
        return self.doc


class _ExtractionRepo:
    def __init__(self, update_returns_rows=True):
        self.row = {"id": 1, "document_id": "doc-1", "status": "approved", "reviewed_by": "u1", "reviewed_at": "t",
                    "validated_json_output": {"owner_name": "Edited"}}
        self.update_returns_rows = update_returns_rows

    def select_one(self, table, filters, order_by=None):
        return self.row

    def update(self, table, filters, payload):
        if not self.update_returns_rows:
            return []
        self.row.update(payload)
        return [self.row]


def _review_service(status, **kwargs):
    docs = _ReviewDocRepo(status)
    extractions = _ExtractionRepo(**kwargs)
    return ReviewService(None, None, docs, extractions, corrections_recorder=object()), docs, extractions


def test_reopening_an_approved_document_returns_it_to_review_and_keeps_edits():
    service, docs, extractions = _review_service("approved")

    result = service.reopen_document_review("doc-1")

    assert docs.doc["status"] == "llm_done"
    assert extractions.row["status"] == "pending_review"
    assert extractions.row["reviewed_at"] is None and extractions.row["reviewed_by"] is None
    assert extractions.row["validated_json_output"] == {"owner_name": "Edited"}
    assert result["document"]["status"] == "llm_done"


def test_a_document_that_was_never_reviewed_cannot_be_reopened():
    service, _, _ = _review_service("llm_done")
    with pytest.raises(PropertySystemException):
        service.reopen_document_review("doc-1")


def test_a_lost_reopen_save_is_reported_not_swallowed():
    service, docs, _ = _review_service("approved", update_returns_rows=False)
    with pytest.raises(PropertySystemException):
        service.reopen_document_review("doc-1")
    assert docs.doc["status"] == "approved"


def test_survey_numbers_and_dates_are_matched_whole():
    pages = [_page(original="Survey No. 12/3 and 12/3/1 and 12/4. Dated 02.04.2019.")]

    terms = find_similar_terms(pages, "12/3")

    by_term = {t["term"]: t["kind"] for t in terms}
    assert by_term["12/3"] == "exact"
    assert by_term["12/3/1"] == "similar"
    assert "12/4" not in by_term  # a different number is not a spelling variant


def test_term_outcome_lists_documents_without_english_text():
    class Pages(_PageRepo):
        def list_by_documents(self, document_ids):
            return [_page(doc="approved-doc", original="पाटील", english="")]

    outcome = _search_service(Pages()).find_terms_outcome("case-1", "पाटील", USER)

    assert outcome["terms"][0]["term"] == "पाटील"
    assert outcome["untranslated_document_ids"] == ["approved-doc"]
