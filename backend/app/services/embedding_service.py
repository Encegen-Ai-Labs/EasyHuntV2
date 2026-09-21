"""
Text embeddings for semantic search — uses the same Gemini client as
llm_extractor.py (no new SDK/dependency needed).

Model note: "gemini-embedding-001" is what actually works against this
project's API key/version — the more commonly referenced
"text-embedding-004" / "models/text-embedding-004" 404s ("not found for API
version v1beta, or not supported for embedContent"). Confirmed by a live call
before wiring this in, not just documentation. If you ever change models,
re-verify live rather than trusting a model name from memory — re-embedding
every existing page would also be required, since old and new vectors aren't
comparable.
"""

from typing import Any, Dict, List, Optional

from google.genai import types

from app.services.llm_extractor import client_genai

EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIMENSIONS = 768


def embed_text(text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> Dict[str, Any]:
    """task_type differs between what's being embedded: "RETRIEVAL_DOCUMENT"
    for page text going into the index, "RETRIEVAL_QUERY" for a search query
    — Gemini's embedding model is trained to place these two asymmetrically so
    a query embedding lands close to relevant document embeddings even when
    the two use different phrasing/length. Using the wrong task_type for
    either side doesn't error, it just ranks worse.

    Never raises — returns {"success": False, "error": ...} on failure so a
    single page's embedding call can't take down the whole pipeline run."""
    if not text or not text.strip():
        return {"success": True, "embedding": None, "error": None}

    try:
        response = client_genai.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=text,
            config=types.EmbedContentConfig(
                output_dimensionality=EMBEDDING_DIMENSIONS,
                task_type=task_type,
            ),
        )
        values = response.embeddings[0].values if response.embeddings else None
        return {"success": True, "embedding": values, "error": None}
    except Exception as e:
        return {"success": False, "embedding": None, "error": str(e)}


def embed_pages(pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """pages: [{"page_number": int, "original_text": str, ...}, ...].
    Returns the same pages with an "embedding" key added (None on failure —
    a page that fails to embed still gets indexed for exact-match search,
    it just won't surface in semantic search results).

    Runs sequentially, not concurrently — matches the same reasoning as
    page_extraction_service.py and translation_service.py: batch upload
    already caps concurrent *documents*, so adding per-page concurrency here
    would multiply how many external calls run at once with no corresponding cap."""
    embedded: List[Dict[str, Any]] = []
    for page in pages:
        result = embed_text(page.get("original_text", ""))
        embedded.append({**page, "embedding": result["embedding"] if result["success"] else None})
    return embedded


def embed_query(query: str) -> Optional[List[float]]:
    """Embeds a search query for semantic search. Returns None on failure —
    the caller falls back to exact-match search rather than erroring."""
    result = embed_text(query, task_type="RETRIEVAL_QUERY")
    return result["embedding"] if result["success"] else None
