from typing import List, Dict, Any, Optional
from app.repositories.base import BaseRepository

class CaseRepository(BaseRepository):
    def create_case(self, case_data: Dict[str, Any]) -> Dict[str, Any]:
        return self.insert("cases", case_data)

    def get_by_id(self, case_id: str) -> Optional[Dict[str, Any]]:
        return self.select_one("cases", {"id": case_id})

    def list_by_vendor(self, vendor_id: str) -> List[Dict[str, Any]]:
        return self.select("cases", {"vendor_id": vendor_id})

    def list_by_reviewer(self, reviewer_id: str) -> List[Dict[str, Any]]:
        return self.select("cases", {"reviewer_id": reviewer_id})

    def list_all(self) -> List[Dict[str, Any]]:
        return self.select("cases")

    def update_case(self, case_id: str, case_data: Dict[str, Any]) -> Dict[str, Any]:
        results = self.update("cases", {"id": case_id}, case_data)
        return results[0] if results else None