from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from app.core.config import settings
from app.core.exceptions import AuthenticationError, PermissionDeniedError
from app.repositories.user_repo import UserRepository
from app.dependencies.db import get_supabase_client
from supabase import Client
from typing import Dict, Any, List

security_bearer = HTTPBearer()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_bearer),
    db: Client = Depends(get_supabase_client)
) -> Dict[str, Any]:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.SUPABASE_JWT_SECRET, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        role: str = payload.get("role")
        if user_id is None or role is None:
            raise AuthenticationError("Malformed JWT claims structure")
    except JWTError:
        raise AuthenticationError("Could not validate credentials")
    
    # Query repository directly
    repo = UserRepository(db)
    user = repo.get_by_id(user_id)
    if not user:
        raise AuthenticationError("User not registered in local schema")
    return user

class RoleRequirement:
    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        if current_user["role"] not in self.allowed_roles:
            raise PermissionDeniedError(f"Operation requires roles: {self.allowed_roles}")
        return current_user