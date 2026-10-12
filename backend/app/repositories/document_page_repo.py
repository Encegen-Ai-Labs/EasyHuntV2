from typing import Any, Dict, List, Optional
from app.repositories.base import BaseRepository

class DocumentPageRepository(BaseRepository):
    def bulk_create(self, pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return self.bulk_insert("document_pages", pages)

    def list_by_document(self, document_id: str) -> List[Dict[str, Any]]:
        return self.select("document_pages", {"document_id": document_id})

    def list_by_documents(self, document_ids: List[str]) -> List[Dict[str, Any]]:
        if not document_ids:
            return []
        return (
            self.client.table("document_pages")
            .select("document_id,page_number,original_text,english_text")
            .in_("document_id", document_ids)
            .execute()
        ).data

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
