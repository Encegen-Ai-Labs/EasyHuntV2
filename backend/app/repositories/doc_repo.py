from typing import Dict, Any, Optional, List
from app.repositories.base import BaseRepository

# A lawyer-approved document: usable for search and for reports. "completed" is
# what finalize_review() sets on an approved case's documents.
APPROVED_STATUSES = {"approved", "completed"}
# Documents the review screen lists: finished processing, whether or not the
# lawyer has decided yet, so an approval can be seen and undone.
REVIEWABLE_STATUSES = {"llm_done", "flagged", "under_review", "approved", "rejected", "completed"}


class DocumentRepository(BaseRepository):
    def create_document(self, doc_data: Dict[str, Any]) -> Dict[str, Any]:
        return self.insert("documents", doc_data)

    def get_by_id(self, doc_id: str) -> Optional[Dict[str, Any]]:
        return self.select_one("documents", {"id": doc_id})

    def update_status(self, doc_id: str, status: str) -> Dict[str, Any]:
        results = self.update("documents", {"id": doc_id}, {"status": status})
        return results[0] if results else None

    def update_file_path(self, doc_id: str, file_path: str) -> Optional[Dict[str, Any]]:
        results = self.update("documents", {"id": doc_id}, {"file_path": file_path})
        return results[0] if results else None

    def list_by_case(self, case_id: str) -> List[Dict[str, Any]]:
        return self.select("documents", {"case_id": case_id})

    def list_reviewable_by_case(self, case_id: str) -> List[Dict[str, Any]]:
        return [
            document
            for document in self.list_by_case(case_id)
            if document.get("status") in REVIEWABLE_STATUSES
        ]

    def list_approved_by_case(self, case_id: str) -> List[Dict[str, Any]]:
        return [
            document
            for document in self.list_by_case(case_id)
            if document.get("status") in APPROVED_STATUSES
        ]