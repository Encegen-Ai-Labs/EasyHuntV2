from typing import Dict, Any, List
from app.repositories.case_repo import CaseRepository
from app.repositories.flag_repo import FlagRepository
from app.core.exceptions import ResourceNotFoundError

class ReviewService:
    def __init__(self, case_repo: CaseRepository, flag_repo: FlagRepository):
        self.case_repo = case_repo
        self.flag_repo = flag_repo

    def resolve_flag(self, flag_id: str, user_id: str, resolution_notes: str, status: str) -> Dict[str, Any]:
        payload = {
            "status": status,
            "resolved_by": user_id,
            "resolution_notes": resolution_notes
        }
        return self.flag_repo.update_flag(flag_id, payload)

    def finalize_review(self, case_id: str, decision: str) -> Dict[str, Any]:
        case_obj = self.case_repo.get_by_id(case_id)
        if not case_obj:
            raise ResourceNotFoundError("Target case not found")
        
        final_status = "completed" if decision == "approve" else "review"
        return self.case_repo.update_case(case_id, {"status": final_status})