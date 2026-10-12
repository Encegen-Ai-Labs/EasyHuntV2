import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any, Dict, List, Set, Tuple

from app.core.config import settings
from app.core.logging import logger
from app.repositories.doc_repo import APPROVED_STATUSES, DocumentRepository
from app.repositories.document_page_repo import DocumentPageRepository
from app.services.doc_service import DocumentService
from app.services.embedding_service import embed_query

SNIPPET_RADIUS = 80  # characters of context shown on each side of the match

# Sentence boundary for snippet selection: standard Latin punctuation plus
# the Devanagari "।" / "॥" danda marks (Marathi/Hindi/etc. sentence-enders,
# which "." alone would miss) and newlines.
_SENTENCE_SPLIT_RE = re.compile(r"[।॥.!?\n]+")


def build_snippet(text: str, query: str, radius: int = SNIPPET_RADIUS) -> str:
    text = text or ""
    idx = text.lower().find(query.lower())
    if idx == -1:
        # Shouldn't normally happen for a row the DB's ILIKE already matched
        # on this same column, but this branch is reachable (a reviewer hit
        # it live 2026-08-21 searching Marathi/Devanagari text; exact
        # mechanism unconfirmed — case-folding differences between
        # Postgres's ILIKE and Python's str.lower() for a given script is
        # the leading theory, not verified against the actual data). The old
        # fallback here (a bare text[:radius*2] slice) meant the reviewer saw
        # a snippet that usually didn't contain the query at all, so <mark>
        # highlighting had nothing to find. Reuse the same word-overlap
        # sentence picker as build_semantic_snippet()'s fallback instead —
        # same defensive intent, a strictly more useful result whenever the
        # query's words appear in a different sentence than .find() expected.
        # NOTE: if the true cause is that the query truly doesn't appear
        # anywhere in this exact text (not just a case-folding quirk), this
        # fallback can't manufacture a highlight either — see project memory
        # for the open question of whether this fully resolves the report.
        return _best_overlapping_sentence(text, query, radius)

    start = max(0, idx - radius)
    end = min(len(text), idx + len(query) + radius)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return f"{prefix}{text[start:end]}{suffix}"


def _best_overlapping_sentence(text: str, query: str, radius: int = SNIPPET_RADIUS) -> str:
    """Picks the sentence (see _SENTENCE_SPLIT_RE) with the most query-word
    overlap, truncated to fit radius*2 chars. Falls back to the first
    radius*2 characters of the whole text if it can't be split into
    sentences at all. Shared by build_snippet()'s no-literal-match fallback
    and build_semantic_snippet()'s no-literal-match fallback."""
    sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]
    if not sentences:
        suffix = "…" if len(text) > radius * 2 else ""
        return text[: radius * 2] + suffix

    query_words = [w for w in re.split(r"\s+", (query or "").lower()) if w]

    def overlap_score(sentence: str) -> int:
        sentence_lower = sentence.lower()
        return sum(1 for w in query_words if w in sentence_lower)

    best = max(sentences, key=overlap_score) if query_words else sentences[0]
    if len(best) <= radius * 2:
        return best
    return best[: radius * 2] + "…"


def build_semantic_snippet(text: str, query: str, radius: int = SNIPPET_RADIUS) -> str:
    """Snippet for a semantic-search result. A page ranked here by embedding
    similarity may or may not also contain the query text literally.

    - If it does, center the snippet on that occurrence via build_snippet()
      — same as exact-mode results — so the frontend's substring-based
      <mark> highlighting actually has something to find, instead of always
      showing (and never highlighting) the page's opening characters
      regardless of where the relevant text actually is.
    - If it doesn't (a genuine semantic-only match, no shared substring),
      fall back to the single sentence with the most word-level overlap
      with the query — a cheap proxy for "most relevant part of this page"
      that needs no extra embedding call. Re-embedding every sentence of
      every result page to rank them properly would multiply this one
      search's embedding cost by (pages returned × sentences per page),
      which isn't worth it for snippet selection alone.
    """
    text = text or ""
    if not text.strip():
        return text

    query = query or ""
    if query.strip() and query.lower() in text.lower():
        return build_snippet(text, query, radius)

    return _best_overlapping_sentence(text, query, radius)


class SearchService:
    def __init__(
        self,
        doc_service: DocumentService,
        doc_repo: DocumentRepository,
        doc_page_repo: DocumentPageRepository,
    ):
        self.doc_service = doc_service
        self.doc_repo = doc_repo
        self.doc_page_repo = doc_page_repo

    def search_case(
        self, case_id: str, query: str, current_user: Dict[str, Any], mode: str = "exact"
    ) -> List[Dict[str, Any]]:
        return self.search_case_with_status(case_id, query, current_user, mode).results

    def search_case_with_status(
        self, case_id: str, query: str, current_user: Dict[str, Any], mode: str = "exact"
    ) -> "SearchOutcome":
        """Exact matches always come first. In "semantic" mode, similar-meaning
        pages follow them (pages already listed as exact matches are not
        repeated), each with a similarity score; the caller shows them as a
        separate, labelled section. If the similar half can't run, the exact
        results are still returned with similar_unavailable=True."""
        # Reuses the same case-ownership rule as upload/case-detail (creator or
        # assigned reviewer, admin unrestricted) instead of a third copy of it.
        self.doc_service.authorize_case_access(case_id, current_user)

        if not query or not query.strip():
            return SearchOutcome(results=[])

        # Search covers only documents the lawyer has approved.
        docs = [d for d in self.doc_repo.list_by_case(case_id) if d.get("status") in APPROVED_STATUSES]
        doc_lookup = {doc["id"]: doc for doc in docs}
        doc_ids = list(doc_lookup.keys())

        exact = self._search_exact(doc_ids, doc_lookup, query)
        if mode != "semantic":
            return SearchOutcome(results=exact)

        already_listed = {(str(r["document_id"]), r["page_number"]) for r in exact}
        similar, unavailable = self._search_similar(doc_ids, doc_lookup, query, already_listed)
        return SearchOutcome(results=exact + similar, similar_unavailable=unavailable)

    def find_terms_outcome(self, case_id: str, query: str, current_user: Dict[str, Any]) -> Dict[str, Any]:
        """find_terms plus the approved documents that have no English text
        yet: an English word cannot match those until they are translated."""
        self.doc_service.authorize_case_access(case_id, current_user)
        docs = [d for d in self.doc_repo.list_by_case(case_id) if d.get("status") in APPROVED_STATUSES]
        if not docs or not query or not query.strip():
            return {"terms": [], "untranslated_document_ids": []}
        pages = self.doc_page_repo.list_by_documents([d["id"] for d in docs])
        translated = {str(p["document_id"]) for p in pages if (p.get("english_text") or "").strip()}
        return {
            "terms": find_similar_terms(pages, query),
            "untranslated_document_ids": [d["id"] for d in docs if str(d["id"]) not in translated],
        }

    def find_terms(self, case_id: str, query: str, current_user: Dict[str, Any]) -> List[Dict[str, Any]]:
        """The words in the approved documents that match, or are close to,
        each word of `query`: the exact word first, then spelling variants.
        The lawyer ticks the ones they mean and the screen highlights those."""
        self.doc_service.authorize_case_access(case_id, current_user)
        if not query or not query.strip():
            return []

        docs = [d for d in self.doc_repo.list_by_case(case_id) if d.get("status") in APPROVED_STATUSES]
        if not docs:
            return []
        pages = self.doc_page_repo.list_by_documents([d["id"] for d in docs])
        return find_similar_terms(pages, query)

    def _search_exact(
        self, doc_ids: List[str], doc_lookup: Dict[str, Dict[str, Any]], query: str
    ) -> List[Dict[str, Any]]:
        pages = self.doc_page_repo.search_by_case(doc_ids, query)

        results: List[Dict[str, Any]] = []
        for page in pages:
            doc = doc_lookup.get(page["document_id"])
            for field in page.get("matched_in", []):
                text_column = "original_text" if field == "original" else "english_text"
                results.append({
                    "document_id": page["document_id"],
                    "document_name": doc.get("file_name") if doc else None,
                    "page_number": page["page_number"],
                    "matched_in": field,
                    "snippet": build_snippet(page.get(text_column, ""), query),
                })

        return results

    def _search_similar(
        self,
        doc_ids: List[str],
        doc_lookup: Dict[str, Dict[str, Any]],
        query: str,
        already_listed: Set[Tuple[str, int]],
    ) -> Tuple[List[Dict[str, Any]], bool]:
        query_embedding = embed_query(query)
        if query_embedding is None:
            # Embedding the query failed (API hiccup, etc.). Say so instead of
            # silently pretending there were no similar passages.
            return [], True

        try:
            pages = self.doc_page_repo.search_by_case_semantic(doc_ids, query_embedding)
        except Exception:
            # e.g. migration 0005 (embedding column / match_document_pages) not
            # applied to this project: keep exact results working.
            logger.exception("search.similar_query_failed | doc_count=%s", len(doc_ids))
            return [], True

        min_similarity = settings.SEARCH_MIN_SIMILARITY
        ranked = sorted(
            (p for p in pages if (p.get("similarity") or 0.0) >= min_similarity),
            key=lambda p: p.get("similarity") or 0.0,
            reverse=True,
        )

        results: List[Dict[str, Any]] = []
        for page in ranked:
            if (str(page["document_id"]), page["page_number"]) in already_listed:
                continue
            doc = doc_lookup.get(page["document_id"])
            text = page.get("original_text") or ""
            results.append({
                "document_id": page["document_id"],
                "document_name": doc.get("file_name") if doc else None,
                "page_number": page["page_number"],
                "matched_in": "semantic",
                "snippet": build_semantic_snippet(text, query),
                "similarity": page.get("similarity"),
            })

        return results, False


# A word is letters/digits/Indic marks, and "12/3", "45-A" or "02.04.2019" stay
# one word so a survey number or a date is matched whole.
_WORD_CHARS = r"[\w\u0900-\u0DFF\u200c\u200d]"
_WORD_RE = re.compile(rf"{_WORD_CHARS}+(?:[/\-.]{_WORD_CHARS}+)*")
# A word must be this close to a query word (difflib ratio) to be offered as a
# spelling variant. 0.72 admits a doubled or swapped vowel in a short name
# ("Patil"/"Pateel" scores 0.73, "Deshmukh"/"Deshmukhh" 0.94) without offering
# unrelated words; the lawyer still chooses which to highlight.
SIMILAR_WORD_MIN_RATIO = 0.72
MAX_SIMILAR_TERMS = 30
MAX_LOCATIONS_PER_TERM = 25


def _normalize_word(word: str) -> str:
    return unicodedata.normalize("NFC", word).casefold()


def find_similar_terms(pages: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
    """Pure core of SearchService.find_terms. Each result:
    {term, kind: "exact"|"similar", count, similarity, locations: [{document_id, page_number}]}.
    "exact" is a word equal to a query word; "similar" is a longer or shorter
    word containing it, or a close spelling. Exact terms come first."""
    query_words = [w for w in dict.fromkeys(_normalize_word(w) for w in _WORD_RE.findall(query)) if w]
    if not query_words:
        return []

    surface: Dict[str, Counter] = defaultdict(Counter)
    counts: Counter = Counter()
    locations: Dict[str, List[Tuple[str, int]]] = defaultdict(list)
    for page in pages:
        for column in ("original_text", "english_text"):
            for raw in _WORD_RE.findall(page.get(column) or ""):
                word = _normalize_word(raw)
                counts[word] += 1
                surface[word][unicodedata.normalize("NFC", raw)] += 1
                location = (str(page["document_id"]), page["page_number"])
                if location not in locations[word] and len(locations[word]) < MAX_LOCATIONS_PER_TERM:
                    locations[word].append(location)

    best: Dict[str, Tuple[str, float]] = {}
    for word in counts:
        for query_word in query_words:
            if word == query_word:
                kind, similarity = "exact", 1.0
            elif len(query_word) >= 3 and len(word) >= 3 and (query_word in word or word in query_word):
                kind = "similar"
                similarity = max(SIMILAR_WORD_MIN_RATIO, SequenceMatcher(None, query_word, word).ratio())
            elif (
                len(query_word) < 3
                or any(ch.isdigit() for ch in query_word)  # a number is exact or different
                or abs(len(word) - len(query_word)) > 3
            ):
                continue
            else:
                ratio = SequenceMatcher(None, query_word, word).ratio()
                if ratio < SIMILAR_WORD_MIN_RATIO:
                    continue
                kind, similarity = "similar", ratio
            if word not in best or similarity > best[word][1]:
                best[word] = (kind, similarity)

    results = [
        {
            "term": surface[word].most_common(1)[0][0],
            "kind": kind,
            "count": counts[word],
            "similarity": round(similarity, 3),
            "locations": [{"document_id": d, "page_number": n} for d, n in locations[word]],
        }
        for word, (kind, similarity) in best.items()
    ]
    exact = sorted((r for r in results if r["kind"] == "exact"), key=lambda r: -r["count"])
    similar = sorted((r for r in results if r["kind"] == "similar"), key=lambda r: (-r["similarity"], -r["count"]))
    return exact + similar[:MAX_SIMILAR_TERMS]


@dataclass
class SearchOutcome:
    results: List[Dict[str, Any]] = field(default_factory=list)
    similar_unavailable: bool = False
