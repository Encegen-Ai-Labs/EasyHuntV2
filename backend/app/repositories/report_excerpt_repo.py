from typing import Any, Dict, List, Optional
from app.repositories.base import BaseRepository

class ReportExcerptRepository(BaseRepository):
    def list_by_report(self, report_id: str) -> List[Dict[str, Any]]:
        rows = self.select("report_excerpts", {"report_id": report_id})
        return sorted(rows, key=lambda r: r["sequence_order"])

    def create(self, excerpt_data: Dict[str, Any]) -> Dict[str, Any]:
        return self.insert("report_excerpts", excerpt_data)

    def get_by_id(self, excerpt_id: str) -> Optional[Dict[str, Any]]:
        return self.select_one("report_excerpts", {"id": excerpt_id})

    def delete_excerpt(self, excerpt_id: str) -> None:
        self.delete("report_excerpts", {"id": excerpt_id})

    def update_note(self, excerpt_id: str, note: Optional[str]) -> Optional[Dict[str, Any]]:
        results = self.update("report_excerpts", {"id": excerpt_id}, {"note": note})
        return results[0] if results else None

    def update_fields(self, excerpt_id: str, fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """General update for excerpt columns — used when the reviewer edits
        excerpt_text alongside (or instead of) note, so both save in one call
        rather than a separate round trip per field."""
        results = self.update("report_excerpts", {"id": excerpt_id}, fields)
        return results[0] if results else None

    def update_sequence(self, excerpt_id: str, sequence_order: int) -> None:
        self.update("report_excerpts", {"id": excerpt_id}, {"sequence_order": sequence_order})
