from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = WORKSPACE_ROOT / ".env"
if not ENV_FILE.exists():
    ENV_FILE = BACKEND_ROOT / ".env"


class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Property Ownership Verification System"
    API_V1_STR: str = "/api/v1"

    # Supabase Credentials
    SUPABASE_URL: str = Field(default="http://127.0.0.1:54321", validation_alias="SUPABASE_URL")
    SUPABASE_KEY: str = Field(default="dev-key", validation_alias="SUPABASE_KEY")
    SUPABASE_SERVICE_ROLE_KEY: str = Field(
        default="",
        validation_alias=AliasChoices("SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_SERVICE_KEY"),
    )
    SUPABASE_JWT_SECRET: str = Field(default="dev-jwt-secret", validation_alias="SUPABASE_JWT_SECRET")

    # Auth configuration
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    ALGORITHM: str = "HS256"
    ADMIN_EMAIL: str = Field(default="", validation_alias="ADMIN_EMAIL")
    ADMIN_PASSWORD: str = Field(default="", validation_alias="ADMIN_PASSWORD")

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

settings = Settings()


def get_supabase_key() -> str:
    return settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_KEY