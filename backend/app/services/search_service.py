import re
import unicodedata
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from typing import Any, Dict, List, Tuple

from app.repositories.doc_repo import APPROVED_STATUSES, DocumentRepository
from app.repositories.document_page_repo import DocumentPageRepository
from app.services.doc_service import DocumentService

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
