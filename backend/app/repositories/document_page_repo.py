from typing import Any, Dict, List, Optional
from app.repositories.base import BaseRepository

def _escape_ilike(text: str) -> str:
    """Escapes ILIKE wildcard characters so a literal '%' or '_' in the search
    term is matched literally — this is exact-keyword search, not wildcard search."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

class DocumentPageRepository(BaseRepository):
    def bulk_create(self, pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return self.bulk_insert("document_pages", pages)

    def list_by_document(self, document_id: str) -> List[Dict[str, Any]]:
        return self.select("document_pages", {"document_id": document_id})

    def update_english_text_bulk(self, document_id: str, pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """pages: [{"page_number": int, "english_text": str}, ...]. One UPDATE
        per page since each page needs a different value — Supabase's update()
        applies a single payload to every row a filter matches, so one bulk
        call can't set a different english_text per row."""
        updated: List[Dict[str, Any]] = []
        for page in pages:
            result = self.update(
                "document_pages",
                {"document_id": document_id, "page_number": page["page_number"]},
                {"english_text": page["english_text"]},
            )
            updated.extend(result)
        return updated

    def update_page_text(self, document_id: str, page_number: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Updates whatever subset of columns `data` contains (original_text,
        english_text, embedding) for a single page — used when a reviewer
        corrects a transcription. Unlike update_english_text_bulk (always sets
        exactly one column across many pages), this sets an arbitrary column
        set for exactly one page. Returns None if no matching row exists."""
        result = self.update(
            "document_pages",
            {"document_id": document_id, "page_number": page_number},
            data,
        )
        return result[0] if result else None

    def search_by_case(self, document_ids: List[str], query: str) -> List[Dict[str, Any]]:
        """Case-insensitive substring match across original_text and english_text,
        scoped to the given document ids (the caller resolves case_id -> document
        ids first, since document_pages only has a document_id column).

        Runs as two separate .ilike() queries (one per column) merged in Python,
        rather than one .or_() filter string — .ilike() takes its pattern as a
        real parameter, so a search term containing PostgREST filter-syntax
        characters (",", ".", etc.) can't reshape the query the way splicing it
        into an .or_() filter string could.
        """
        if not document_ids or not query.strip():
            return []

        pattern = f"%{_escape_ilike(query)}%"

        original_matches = (
            self.client.table("document_pages")
            .select("*")
            .in_("document_id", document_ids)
            .ilike("original_text", pattern)
            .execute()
        ).data

        english_matches = (
            self.client.table("document_pages")
            .select("*")
            .in_("document_id", document_ids)
            .ilike("english_text", pattern)
            .execute()
        ).data

        merged: Dict[str, Dict[str, Any]] = {}
        for row in original_matches:
            merged[row["id"]] = {**row, "matched_in": ["original"]}
        for row in english_matches:
            if row["id"] in merged:
                merged[row["id"]]["matched_in"].append("english")
            else:
                merged[row["id"]] = {**row, "matched_in": ["english"]}

        return list(merged.values())

    def search_by_case_semantic(
        self, document_ids: List[str], query_embedding: List[float], limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Semantic search via the match_document_pages Postgres function
        (migrations/0005_document_pages_embedding.sql) — pgvector's distance
        operator isn't reachable through supabase-py's REST filter DSL, only
        via .rpc(). Each result carries a "similarity" score (0..1, higher is
        more relevant) instead of search_by_case()'s offset/length, since
        there's no literal substring match to point at.
        """
        if not document_ids or not query_embedding:
            return []

        response = self.client.rpc(
            "match_document_pages",
            {
                "query_embedding": query_embedding,
                "match_document_ids": document_ids,
                "match_count": limit,
            },
        ).execute()
        return response.data or []
