import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Property Ownership Verification System"
    API_V1_STR: str = "/api/v1"

    # Supabase Credentials
    SUPABASE_URL: str = Field(default="http://127.0.0.1:54321", validation_alias="SUPABASE_URL")
    SUPABASE_KEY: str = Field(default="dev-key", validation_alias="SUPABASE_KEY")
    SUPABASE_JWT_SECRET: str = Field(default="dev-jwt-secret", validation_alias="SUPABASE_JWT_SECRET")

    # Auth configuration
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    ALGORITHM: str = "HS256"
    ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()