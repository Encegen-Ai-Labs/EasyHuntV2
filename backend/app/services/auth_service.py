from typing import Dict, Any, List
from app.repositories.user_repo import UserRepository
from app.core.security import get_password_hash, verify_password, create_access_token
from app.core.exceptions import AuthenticationError, PropertySystemException
from app.schemas.auth import UserRegister, UserLogin

class AuthService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    def register_user(self, schema: UserRegister) -> Dict[str, Any]:
        existing = self.user_repo.get_by_email(schema.email)
        if existing:
            raise PropertySystemException("Email is already registered")
        
        user_payload = {
            "email": schema.email,
            "hashed_password": get_password_hash(schema.password),
            "full_name": schema.full_name,
            "role": schema.role.value,
            "is_active": True
        }
        return self.user_repo.create_user(user_payload)

    def login_user(self, schema: UserLogin) -> Dict[str, Any]:
        user = self.user_repo.get_by_email(schema.email)
        if not user or not verify_password(schema.password, user["hashed_password"]):
            raise AuthenticationError("Invalid email or password provided")
        
        if not user["is_active"]:
            raise AuthenticationError("User account is inactive")
        
        access_token = create_access_token(data={"sub": user["id"], "role": user["role"]})
        return {"access_token": access_token, "token_type": "bearer"}

    def get_user_by_id(self, user_id: str) -> Dict[str, Any]:
        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise AuthenticationError("User not found")
        return user