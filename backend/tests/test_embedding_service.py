"""Tests for app/services/embedding_service.py — Gemini calls are mocked
(matching test_translation_service.py's pattern for the equivalent external
API), so these don't need a live key or network access."""

from app.services import embedding_service


class FakeEmbedding:
    def __init__(self, values):
        self.values = values


class FakeEmbedContentResponse:
    def __init__(self, values):
        self.embeddings = [FakeEmbedding(values)] if values is not None else []


def test_embed_text_empty_string_short_circuits(monkeypatch):
    def _fail_if_called(**kwargs):
        raise AssertionError("embed_content should not be called for empty text")

    monkeypatch.setattr(embedding_service.client_genai.models, "embed_content", _fail_if_called)

    result = embedding_service.embed_text("   ")

    assert result == {"success": True, "embedding": None, "error": None}


def test_embed_text_success_returns_vector(monkeypatch):
    fake_vector = [0.1] * 768

    def fake_embed_content(**kwargs):
        assert kwargs["model"] == embedding_service.EMBEDDING_MODEL
        assert kwargs["contents"] == "a sale deed"
        return FakeEmbedContentResponse(fake_vector)

    monkeypatch.setattr(embedding_service.client_genai.models, "embed_content", fake_embed_content)

    result = embedding_service.embed_text("a sale deed")

    assert result["success"] is True
    assert result["embedding"] == fake_vector
    assert len(result["embedding"]) == embedding_service.EMBEDDING_DIMENSIONS


def test_embed_text_uses_different_task_type_for_query_vs_document(monkeypatch):
    seen_task_types = []

    def fake_embed_content(**kwargs):
        seen_task_types.append(kwargs["config"].task_type)
        return FakeEmbedContentResponse([0.0] * 768)

    monkeypatch.setattr(embedding_service.client_genai.models, "embed_content", fake_embed_content)

    embedding_service.embed_text("page text", task_type="RETRIEVAL_DOCUMENT")
    embedding_service.embed_query("search query")

    assert seen_task_types == ["RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY"]


def test_embed_text_api_failure_returns_error_without_raising(monkeypatch):
    def failing_embed_content(**kwargs):
        raise RuntimeError("quota exceeded")

    monkeypatch.setattr(embedding_service.client_genai.models, "embed_content", failing_embed_content)

    result = embedding_service.embed_text("some text")

    assert result["success"] is False
    assert "quota exceeded" in result["error"]


def test_embed_query_returns_none_on_failure(monkeypatch):
    monkeypatch.setattr(
        embedding_service.client_genai.models, "embed_content",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("down")),
    )

    assert embedding_service.embed_query("anything") is None


def test_embed_pages_adds_embedding_per_page(monkeypatch):
    def fake_embed_content(**kwargs):
        # Different vector per call so we can tell pages apart in the assertion.
        text = kwargs["contents"]
        return FakeEmbedContentResponse([len(text)] * 768)

    monkeypatch.setattr(embedding_service.client_genai.models, "embed_content", fake_embed_content)

    pages = [
        {"page_number": 1, "original_text": "hi"},
        {"page_number": 2, "original_text": "hello there"},
    ]
    result = embedding_service.embed_pages(pages)

    assert result[0]["embedding"][0] == 2
    assert result[1]["embedding"][0] == 11
    # original page fields preserved
    assert result[0]["page_number"] == 1


def test_embed_pages_keeps_page_with_null_embedding_on_failure(monkeypatch):
    def flaky_embed_content(**kwargs):
        if kwargs["contents"] == "bad":
            raise RuntimeError("boom")
        return FakeEmbedContentResponse([0.5] * 768)

    monkeypatch.setattr(embedding_service.client_genai.models, "embed_content", flaky_embed_content)

    pages = [
        {"page_number": 1, "original_text": "bad"},
        {"page_number": 2, "original_text": "good"},
    ]
    result = embedding_service.embed_pages(pages)

    assert result[0]["embedding"] is None
    assert result[1]["embedding"] == [0.5] * 768
