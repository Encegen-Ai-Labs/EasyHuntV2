from typing import Optional, Dict, Any, List
from app.repositories.base import BaseRepository

class UserRepository(BaseRepository):
    def get_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        return self.select_one("users", {"email": email})

    def get_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        return self.select_one("users", {"id": user_id})

    def create_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        return self.insert("users", user_data)

    def list_all_users(self) -> List[Dict[str, Any]]:
        return self.select("users")

    def delete_user(self, user_id: str) -> bool:
        self.delete("users", {"id": user_id})
        return True