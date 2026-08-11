from pydantic import BaseModel, EmailStr, Field
from enum import Enum
from typing import Optional
from uuid import UUID
from datetime import datetime

class RoleEnum(str, Enum):
    Admin = "Admin"
    Reviewer = "Reviewer"
    Vendor = "Vendor"

class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    organisation_name: str
    role: RoleEnum = RoleEnum.Vendor

class ReviewerCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    organisation_name: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    organisation_name: str
    role: RoleEnum
    created_at: datetime

    class Config:
        from_attributes = True