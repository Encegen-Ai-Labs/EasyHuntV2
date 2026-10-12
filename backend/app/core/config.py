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

    # Browser origins allowed to call the API (CORS), comma separated.
    CORS_ORIGINS: str = Field(default="http://localhost:3000", validation_alias="CORS_ORIGINS")

    # Auth configuration
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    ALGORITHM: str = "HS256"
    ADMIN_EMAIL: str = Field(default="", validation_alias="ADMIN_EMAIL")
    ADMIN_PASSWORD: str = Field(default="", validation_alias="ADMIN_PASSWORD")

    # Document processing can use the durable Celery queue when Redis is
    # available. Local development keeps the existing FastAPI background-task
    # path unless CELERY_ENABLED is explicitly enabled.
    CELERY_ENABLED: bool = Field(default=False, validation_alias="CELERY_ENABLED")
    CELERY_BROKER_URL: str = Field(
        default="redis://localhost:6379/0",
        validation_alias="CELERY_BROKER_URL",
    )
    # Documents processed at once per worker process. Each document fans out to
    # up to MAX_CONCURRENT_PAGES_PER_DOCUMENT concurrent Gemini calls, so the
    # worst case in flight is workers x this x 4. Hard-capped in celery_app.py.
    CELERY_WORKER_CONCURRENCY: int = Field(default=3, validation_alias="CELERY_WORKER_CONCURRENCY")
    # Backoff when Gemini rate-limits a document: base * 2^attempt seconds, plus jitter.
    CELERY_RATE_LIMIT_RETRIES: int = Field(default=5, validation_alias="CELERY_RATE_LIMIT_RETRIES")
    CELERY_RATE_LIMIT_BACKOFF_SECONDS: int = Field(
        default=30, validation_alias="CELERY_RATE_LIMIT_BACKOFF_SECONDS"
    )

    # ---- Search ----
    # Similar-meaning search returns the closest pages by embedding distance no
    # matter how weak the match, so drop pages below this cosine similarity.
    # Deliberately permissive until it can be calibrated on real case data
    # (including Marathi/Hindi pages); the UI shows each match's similarity so a
    # reviewer can judge weak ones. Raise it if the "Similar" section is noisy.
    SEARCH_MIN_SIMILARITY: float = Field(default=0.30, validation_alias="SEARCH_MIN_SIMILARITY")

    # ---- Extraction cache (app/services/extraction_cache.py) ----
    # Reuse the stored extraction when the exact same file (same bytes) was already
    # extracted with the same model and pipeline version. OFF by default: it needs
    # migrations/0007_extraction_cache.sql applied first. A lawyer can bypass it per
    # upload (force_refresh). Failures are never cached.
    EXTRACTION_CACHE_ENABLED: bool = Field(default=False, validation_alias="EXTRACTION_CACHE_ENABLED")

    # ---- Document router (OCR vs VLM routing, app/services/document_router.py) ----
    # Handwritten-area ratio at or above which a page is routed to the VLM instead
    # of the (faster, cheaper) OCR path. ratio = handwritten box area / total box area.
    ROUTER_HANDWRITING_THRESHOLD: float = Field(default=0.10, validation_alias="ROUTER_HANDWRITING_THRESHOLD")
    # If OCR confidence on a page routed to OCR falls below this, the router
    # escalates that page to the VLM rather than trust a low-confidence OCR read.
    OCR_FALLBACK_CONFIDENCE: float = Field(default=0.70, validation_alias="OCR_FALLBACK_CONFIDENCE")
    # Optional override for the Tesseract binary path — leave unset to resolve
    # "tesseract" from PATH (pytesseract's default behavior).
    TESSERACT_CMD_PATH: str = Field(default="", validation_alias="TESSERACT_CMD_PATH")

    # Tesseract language models to load, "+"-joined (pytesseract's own format
    # for multi-language OCR — it tries all of them per word/line and keeps
    # the best match). Defaults to English plus the regional Indian scripts
    # this app's own prompts (llm_extractor.py, page_extraction_service.py)
    # already say these documents can be in. Without a non-English language
    # pack actually installed for a given code here, Tesseract can't read
    # that script at all — a page in it gets ~0 confidence regardless of
    # scan/enhancement quality and always escalates to the VLM (see
    # tesseract_provider.py). This only takes effect once the matching
    # .traineddata files are installed in Tesseract's tessdata directory —
    # changing this setting alone doesn't install them.
    TESSERACT_LANGUAGES: str = Field(default="eng+hin+mar+tam+tel+kan", validation_alias="TESSERACT_LANGUAGES")

    # ---- Environment and safety ----
    # "development" (default), "staging" or "production". Production refuses to
    # start on placeholder secrets (see app/core/startup_checks.py) and logs JSON.
    APP_ENV: str = Field(default="development", validation_alias="APP_ENV")
    # Secret that signs this app's own login tokens. When unset the Supabase JWT
    # secret is used (the old behaviour), but a separate value is safer: the
    # Supabase secret also grants access to the database API.
    APP_JWT_SECRET: str = Field(default="", validation_alias="APP_JWT_SECRET")
    # Error tracking. Empty = off. Request bodies, headers and document text are
    # never sent (see app/core/observability.py).
    SENTRY_DSN: str = Field(default="", validation_alias="SENTRY_DSN")

    # ---- Rate limiting (app/core/rate_limiting.py) ----
    # Only true behind a reverse proxy you control: then the client address is
    # taken from X-Forwarded-For. Otherwise that header is attacker-controlled.
    TRUST_PROXY: bool = Field(default=False, validation_alias="TRUST_PROXY")
    RATE_LIMIT_ENABLED: bool = Field(default=True, validation_alias="RATE_LIMIT_ENABLED")
    # "memory://" works for one process; docker-compose points it at Redis so the
    # limits are shared by every API process.
    RATE_LIMIT_STORAGE_URL: str = Field(default="memory://", validation_alias="RATE_LIMIT_STORAGE_URL")
    RATE_LIMIT_LOGIN: str = Field(default="10/minute", validation_alias="RATE_LIMIT_LOGIN")
    RATE_LIMIT_UPLOAD: str = Field(default="20/minute", validation_alias="RATE_LIMIT_UPLOAD")
    # Calls that spend money (translation, report drafting) are limited per user.
    RATE_LIMIT_PAID_CALLS: str = Field(default="20/minute", validation_alias="RATE_LIMIT_PAID_CALLS")
    RATE_LIMIT_DEFAULT: str = Field(default="300/minute", validation_alias="RATE_LIMIT_DEFAULT")

    # ---- LLM usage and cost (app/services/llm_usage.py) ----
    # ESTIMATES in US dollars per million tokens (per million characters for
    # Cloud Translation). Check them against Google's current price list for the
    # model in use and override here; the dashboard labels cost as an estimate.
    LLM_PRICE_INPUT_PER_M: float = Field(default=0.10, validation_alias="LLM_PRICE_INPUT_PER_M")
    LLM_PRICE_OUTPUT_PER_M: float = Field(default=0.40, validation_alias="LLM_PRICE_OUTPUT_PER_M")
    LLM_PRICE_EMBEDDING_PER_M: float = Field(default=0.15, validation_alias="LLM_PRICE_EMBEDDING_PER_M")
    TRANSLATE_PRICE_PER_M_CHARS: float = Field(default=20.0, validation_alias="TRANSLATE_PRICE_PER_M_CHARS")
    # When today's estimated spend reaches this, new uploads, translations and
    # report drafts are refused with a clear message (work already running
    # finishes). 0 turns the guard off.
    DAILY_LLM_BUDGET_USD: float = Field(default=0.0, validation_alias="DAILY_LLM_BUDGET_USD")

    # ---- Translation (app/services/translation_service.py) ----
    # "auto": Google Cloud Translation when GOOGLE_TRANSLATE_API_KEY works, else
    # Gemini. "google" or "gemini" force one.
    TRANSLATION_PROVIDER: str = Field(default="auto", validation_alias="TRANSLATION_PROVIDER")

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() == "production"

    @property
    def jwt_signing_secret(self) -> str:
        return self.APP_JWT_SECRET or self.SUPABASE_JWT_SECRET

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()


def get_supabase_key() -> str:
    return settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_KEY