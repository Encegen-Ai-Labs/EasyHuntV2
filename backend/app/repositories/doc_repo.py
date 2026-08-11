from typing import Dict, Any, Optional, List
from app.repositories.base import BaseRepository

class DocumentRepository(BaseRepository):
    def create_document(self, doc_data: Dict[str, Any]) -> Dict[str, Any]:
        return self.insert("documents", doc_data)

    def get_by_id(self, doc_id: str) -> Optional[Dict[str, Any]]:
        return self.select_one("documents", {"id": doc_id})

    def update_status(self, doc_id: str, status: str) -> Dict[str, Any]:
        results = self.update("documents", {"id": doc_id}, {"status": status})
        return results[0] if results else None

    def list_by_case(self, case_id: str) -> List[Dict[str, Any]]:
        return self.select("documents", {"case_id": case_id})

    def list_reviewable_by_case(self, case_id: str) -> List[Dict[str, Any]]:
        return [
            document
            for document in self.list_by_case(case_id)
            if document.get("status") in {"llm_done", "flagged", "under_review"}
        ]