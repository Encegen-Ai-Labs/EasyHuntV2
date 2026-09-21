import pytest
from fastapi.testclient import TestClient

from app.api.v1.search import get_search_service
from app.core.exceptions import PermissionDeniedError
from app.dependencies.auth import get_current_user
from app.main import app
from app.services.doc_service import DocumentService
from app.services.search_service import SearchService, build_semantic_snippet, build_snippet


class FakeCaseRepo:
    def __init__(self, case_obj=None):
        self.case_obj = case_obj or {"id": "case-1", "created_by": "reviewer-1"}

    def get_by_id(self, case_id):
        return self.case_obj if self.case_obj.get("id") == case_id else None


class FakeDocRepo:
    def __init__(self, docs=None):
        self.docs = docs or [{"id": "doc-1", "case_id": "case-1", "file_name": "sale_deed.pdf"}]

    def list_by_case(self, case_id):
        return [d for d in self.docs if d.get("case_id") == case_id]


class FakeDocumentPageRepo:
    def __init__(self, pages=None, semantic_pages=None):
        self.pages = pages if pages is not None else []
        self.semantic_pages = semantic_pages if semantic_pages is not None else []
        self.last_call = None
        self.last_semantic_call = None

    def search_by_case(self, document_ids, query):
        self.last_call = (document_ids, query)
        return self.pages

    def search_by_case_semantic(self, document_ids, query_embedding, limit=20):
        self.last_semantic_call = (document_ids, query_embedding, limit)
        return self.semantic_pages


# --- build_snippet ---

def test_build_snippet_adds_ellipsis_on_both_sides_for_a_middle_match():
    text = "x" * 100 + "TARGET" + "y" * 100
    snippet = build_snippet(text, "TARGET", radius=10)

    assert snippet.startswith("…")
    assert snippet.endswith("…")
    assert "TARGET" in snippet


def test_build_snippet_omits_leading_ellipsis_when_match_is_at_the_start():
    text = "TARGET" + "y" * 100
    snippet = build_snippet(text, "TARGET", radius=10)

    assert not snippet.startswith("…")
    assert snippet.startswith("TARGET")


def test_build_snippet_omits_trailing_ellipsis_when_match_is_at_the_end():
    text = "x" * 100 + "TARGET"
    snippet = build_snippet(text, "TARGET", radius=10)

    assert not snippet.endswith("…")
    assert snippet.endswith("TARGET")


def test_build_snippet_is_case_insensitive():
    snippet = build_snippet("some Target text", "target")
    assert "Target" in snippet


def test_build_snippet_falls_back_to_overlapping_sentence_when_python_find_misses():
    # Simulates the observed live bug (2026-08-21): a row the DB's ILIKE
    # matched but whose text .lower().find() doesn't locate the query in
    # (script/collation-folding mismatch) — the query itself never appears
    # literally in the text passed here, so .find() always misses. The
    # fallback must not silently return an arbitrary early slice; it should
    # pick whichever sentence actually shares words with the query.
    text = "अनोळखी वाक्य येथे आहे. दिनांक विषयी वाक्य येथे आहे. आणखी एक वाक्य."
    snippet = build_snippet(text, "दिनांक निश्चित", radius=40)

    assert "दिनांक विषयी वाक्य येथे आहे" in snippet


# --- build_semantic_snippet ---

def test_build_semantic_snippet_centers_on_literal_match_when_query_appears_in_text():
    # If the query text happens to appear literally in a semantically-ranked
    # page, the snippet should be built the same match-centered way as exact
    # search, so the frontend's substring highlighting can actually find it
    # instead of only ever showing (and never highlighting) the page's start.
    text = "x" * 100 + "दिनांक" + "y" * 100
    snippet = build_semantic_snippet(text, "दिनांक", radius=10)

    assert "दिनांक" in snippet
    assert snippet.startswith("…")
    assert snippet.endswith("…")


def test_build_semantic_snippet_picks_most_overlapping_sentence_without_literal_match():
    text = "पहिले वाक्य असंबंधित आहे. मालमत्तेची नोंदणी तारीख नमूद आहे. तिसरे वाक्य वेगळे आहे."
    snippet = build_semantic_snippet(text, "नोंदणी तारीख", radius=80)

    assert "मालमत्तेची नोंदणी तारीख नमूद आहे" in snippet


def test_build_semantic_snippet_handles_empty_text():
    assert build_semantic_snippet("", "दिनांक") == ""


# --- SearchService ---

def test_search_case_reuses_authorize_case_access_and_blocks_unrelated_reviewer():
    case_repo = FakeCaseRepo({"id": "case-1", "created_by": "someone-else"})
    doc_repo = FakeDocRepo()
    doc_service = DocumentService(doc_repo=None, case_repo=case_repo)  # only authorize_case_access is exercised
    service = SearchService(doc_service, doc_repo, FakeDocumentPageRepo())

    with pytest.raises(PermissionDeniedError):
        service.search_case("case-1", "deed", {"id": "reviewer-1", "role": "Reviewer"})


def test_search_case_returns_empty_list_for_blank_query_without_querying_pages():
    case_repo = FakeCaseRepo()
    doc_repo = FakeDocRepo()
    doc_service = DocumentService(doc_repo=None, case_repo=case_repo)
    page_repo = FakeDocumentPageRepo()
    service = SearchService(doc_service, doc_repo, page_repo)

    result = service.search_case("case-1", "   ", {"id": "reviewer-1", "role": "Reviewer"})

    assert result == []
    assert page_repo.last_call is None


def test_search_case_expands_a_row_matched_in_both_columns_into_two_results():
    case_repo = FakeCaseRepo()
    doc_repo = FakeDocRepo()
    doc_service = DocumentService(doc_repo=None, case_repo=case_repo)
    page_repo = FakeDocumentPageRepo(pages=[
        {
            "id": "page-1",
            "document_id": "doc-1",
            "page_number": 3,
            "original_text": "यह भूमि सर्वे नंबर 45 है",
            "english_text": "this is survey number 45 land",
            "matched_in": ["original", "english"],
        }
    ])
    service = SearchService(doc_service, doc_repo, page_repo)

    results = service.search_case("case-1", "45", {"id": "reviewer-1", "role": "Reviewer"})

    assert page_repo.last_call == (["doc-1"], "45")
    assert len(results) == 2
    matched_fields = {r["matched_in"] for r in results}
    assert matched_fields == {"original", "english"}
    for r in results:
        assert r["document_id"] == "doc-1"
        assert r["document_name"] == "sale_deed.pdf"
        assert r["page_number"] == 3
        assert "45" in r["snippet"]


def test_search_case_handles_document_with_no_matching_page_gracefully():
    case_repo = FakeCaseRepo()
    doc_repo = FakeDocRepo()
    doc_service = DocumentService(doc_repo=None, case_repo=case_repo)
    page_repo = FakeDocumentPageRepo(pages=[])
    service = SearchService(doc_service, doc_repo, page_repo)

    results = service.search_case("case-1", "nonexistent", {"id": "reviewer-1", "role": "Reviewer"})

    assert results == []


# --- semantic mode ---

def test_search_case_semantic_embeds_query_and_ranks_by_similarity(monkeypatch):
    from app.services import search_service as search_svc

    case_repo = FakeCaseRepo()
    doc_repo = FakeDocRepo()
    doc_service = DocumentService(doc_repo=None, case_repo=case_repo)
    page_repo = FakeDocumentPageRepo(semantic_pages=[
        {"document_id": "doc-1", "page_number": 3, "original_text": "sale deed executed transferring ownership", "similarity": 0.83},
    ])
    service = SearchService(doc_service, doc_repo, page_repo)

    monkeypatch.setattr(search_svc, "embed_query", lambda q: [0.1, 0.2, 0.3])

    results = service.search_case("case-1", "transfer of ownership", {"id": "reviewer-1", "role": "Reviewer"}, mode="semantic")

    assert page_repo.last_semantic_call[1] == [0.1, 0.2, 0.3]
    assert len(results) == 1
    assert results[0]["matched_in"] == "semantic"
    assert results[0]["similarity"] == 0.83
    assert results[0]["document_name"] == "sale_deed.pdf"


def test_search_case_semantic_falls_back_to_exact_when_query_embedding_fails(monkeypatch):
    from app.services import search_service as search_svc

    case_repo = FakeCaseRepo()
    doc_repo = FakeDocRepo()
    doc_service = DocumentService(doc_repo=None, case_repo=case_repo)
    page_repo = FakeDocumentPageRepo(pages=[
        {"id": "p1", "document_id": "doc-1", "page_number": 1, "original_text": "fallback match", "matched_in": ["original"]},
    ])
    service = SearchService(doc_service, doc_repo, page_repo)

    monkeypatch.setattr(search_svc, "embed_query", lambda q: None)

    results = service.search_case("case-1", "fallback", {"id": "reviewer-1", "role": "Reviewer"}, mode="semantic")

    # Fell back to exact search rather than erroring or returning nothing.
    assert page_repo.last_call is not None
    assert len(results) == 1
    assert results[0]["matched_in"] == "original"


# --- route wiring ---

def test_search_route_returns_results_from_service():
    class StubSearchService:
        def search_case(self, case_id, query, current_user, mode="exact"):
            assert case_id == "case-1"
            assert query == "45"
            return [{
                "document_id": "11111111-1111-1111-1111-111111111111",
                "document_name": "deed.pdf",
                "page_number": 2,
                "matched_in": "original",
                "snippet": "...survey 45...",
            }]

    app.dependency_overrides[get_current_user] = lambda: {"id": "reviewer-1", "role": "Reviewer"}
    app.dependency_overrides[get_search_service] = lambda: StubSearchService()

    client = TestClient(app)
    response = client.get(
        "/api/v1/cases/case-1/search",
        params={"q": "45"},
        headers={"Authorization": "Bearer test-token"},
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "45"
    assert len(body["results"]) == 1
    assert body["results"][0]["page_number"] == 2
    assert body["results"][0]["document_name"] == "deed.pdf"


def test_search_route_requires_q_param():
    class StubSearchService:
        def search_case(self, case_id, query, current_user, mode="exact"):
            raise AssertionError("service should not be reached when q is missing")

    app.dependency_overrides[get_current_user] = lambda: {"id": "reviewer-1", "role": "Reviewer"}
    app.dependency_overrides[get_search_service] = lambda: StubSearchService()

    client = TestClient(app)
    response = client.get("/api/v1/cases/case-1/search")

    app.dependency_overrides.clear()

    assert response.status_code == 422
