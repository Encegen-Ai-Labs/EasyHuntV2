from typing import List, Dict, Any
from app.repositories.base import BaseRepository

class FlagRepository(BaseRepository):
    def create_flag(self, flag_data: Dict[str, Any]) -> Dict[str, Any]:
        return self.insert("flags", flag_data)

    def list_by_case(self, case_id: str) -> List[Dict[str, Any]]:
        return self.select("flags", {"case_id": case_id})

    def update_flag(self, flag_id: str, flag_data: Dict[str, Any]) -> Dict[str, Any]:
        results = self.update("flags", {"id": flag_id}, flag_data)
        return results[0] if results else None