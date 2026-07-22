from typing import List, Dict, Any, Optional
from app.repositories.case_repo import CaseRepository
from app.core.exceptions import ResourceNotFoundError, PermissionDeniedError

class CaseService:
    def __init__(self, case_repo: CaseRepository):
        self.case_repo = case_repo

    def create(self, vendor_id: str, property_address: str, survey_number: str) -> Dict[str, Any]:
        payload = {
            "vendor_id": vendor_id,
            "property_address": property_address,
            "survey_number": survey_number,
            "status": "open"
        }
        return self.case_repo.create_case(payload)

    def retrieve(self, case_id: str, current_user: Dict[str, Any]) -> Dict[str, Any]:
        case_item = self.case_repo.get_by_id(case_id)
        if not case_item:
            raise ResourceNotFoundError("Case not found")
        
        # Enforce multi-tenant access boundaries
        if current_user["role"] == "Vendor" and case_item["vendor_id"] != current_user["id"]:
            raise PermissionDeniedError("You can only access your own cases")
        return case_item

    def list_cases(self, current_user: Dict[str, Any]) -> List[Dict[str, Any]]:
        role = current_user["role"]
        if role == "Admin":
            return self.case_repo.list_all()
        elif role == "Reviewer":
            return self.case_repo.list_by_reviewer(current_user["id"])
        else:
            return self.case_repo.list_by_vendor(current_user["id"])