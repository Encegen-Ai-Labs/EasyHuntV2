from typing import Dict, Any, Optional
from app.repositories.base import BaseRepository

class ReportRepository(BaseRepository):
    def create_report(self, report_data: Dict[str, Any]) -> Dict[str, Any]:
        return self.insert("reports", report_data)

    def get_by_case(self, case_id: str) -> Optional[Dict[str, Any]]:
        return self.select_one("reports", {"case_id": case_id})