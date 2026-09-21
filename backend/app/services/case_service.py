from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from app.repositories.case_repo import CaseRepository
from app.core.exceptions import ResourceNotFoundError, PermissionDeniedError

class CaseService:
    def __init__(self, case_repo: CaseRepository):
        self.case_repo = case_repo

    def create(
        self,
        creator_id: str,
        property_name: str,
        survey_number: str,
        location: Optional[str] = None
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()

        payload = {
            "created_by": creator_id,
            "property_name": property_name,
            "survey_number": survey_number,
            "location": location,
            "status": "open",
            "created_at": now,
            "updated_at": now
        }
        return self.case_repo.create_case(payload)

    def retrieve(self, case_id: str, current_user: Dict[str, Any]) -> Dict[str, Any]:
        case_item = self.case_repo.get_by_id(case_id)
        if not case_item:
            raise ResourceNotFoundError("Case not found")

        if current_user["role"] == "Reviewer":
            owns_case = (
                case_item.get("created_by") == current_user["id"]
                or case_item.get("reviewer_id") == current_user["id"]
            )
            if not owns_case:
                raise PermissionDeniedError("You can only access cases you created or have been assigned to review")
        return case_item

    def list_cases(self, current_user: Dict[str, Any]) -> List[Dict[str, Any]]:
        role = current_user["role"]
        if role == "Admin":
            return self.case_repo.list_all()
        # Reviewer: cases they created, or that an admin has assigned them to review
        return self.case_repo.list_owned_by(current_user["id"])