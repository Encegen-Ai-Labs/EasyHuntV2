from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Property Ownership Verification System"
    API_V1_STR: str = "/api/v1"

    # Supabase Credentials
    SUPABASE_URL: str = Field(default="http://127.0.0.1:54321", validation_alias="SUPABASE_URL")
    SUPABASE_KEY: str = Field(default="dev-key", validation_alias="SUPABASE_KEY")
    SUPABASE_SERVICE_ROLE_KEY: str = Field(default="", validation_alias="SUPABASE_SERVICE_ROLE_KEY")
    SUPABASE_JWT_SECRET: str = Field(default="dev-jwt-secret", validation_alias="SUPABASE_JWT_SECRET")

    # Auth configuration
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    ALGORITHM: str = "HS256"
    ADMIN_EMAIL: str = Field(default="", validation_alias="ADMIN_EMAIL")
    ADMIN_PASSWORD: str = Field(default="", validation_alias="ADMIN_PASSWORD")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()


def get_supabase_key() -> str:
    return settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_KEY