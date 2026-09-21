from typing import Dict, Any, Optional
from app.repositories.base import BaseRepository

class ReportRepository(BaseRepository):
    def create_report(self, report_data: Dict[str, Any]) -> Dict[str, Any]:
        return self.insert("reports", report_data)

    def get_by_case(self, case_id: str) -> Optional[Dict[str, Any]]:
        return self.select_one("reports", {"case_id": case_id})

    def get_by_case_and_type(self, case_id: str, report_type: str) -> Optional[Dict[str, Any]]:
        """Distinguishes the manual report builder's row from the pre-existing
        LLM-draft/PDF-summary rows that already share this table — see
        migrations/0003_report_excerpts.sql. get_by_case() above is untouched so
        the existing PDF-download flow (reports.py) keeps its current behavior."""
        return self.select_one("reports", {"case_id": case_id, "report_type": report_type})

    def update_file_path(self, report_id: str, file_path: str) -> Optional[Dict[str, Any]]:
        # The live reports table's PDF column is actually named "pdf_path",
        # not "file_path" — this method's own name/param stay as-is since
        # callers (report_builder_service.py) don't need to change, only the
        # column this writes to.
        results = self.update("reports", {"id": report_id}, {"pdf_path": file_path})
        return results[0] if results else None