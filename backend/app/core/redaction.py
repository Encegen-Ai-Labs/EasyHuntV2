"""Keeps secrets out of anything that is logged, stored or shown to a user.

Two layers, because neither alone is enough:
- the *values* of the secrets this app is configured with (an API key is
  scrubbed even when it appears in a form no pattern would recognise);
- patterns for the usual shapes (a `key=` query parameter, a Bearer token, a
  JWT, Google and OpenAI-style keys).

The first leak this guards against is real: an httpx error message contains the
full request URL, and the Translation API takes its key in the URL, so a failed
call produced "...v2?key=<the key>", which was saved as page text and shown on
screen. Anything that turns an exception into text should go through redact().
"""
import os
import re

REDACTED = "[redacted]"

# Environment variables whose values are secrets. Read on every call, so a key
# set after import (tests, a reloaded .env) is still covered.
SECRET_ENV_NAMES = (
    "GEMINI_API_KEY",
    "GOOGLE_TRANSLATE_API_KEY",
    "SUPABASE_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
    "SUPABASE_SERVICE_KEY",
    "SUPABASE_JWT_SECRET",
    "APP_JWT_SECRET",
    "ADMIN_PASSWORD",
    "SENTRY_DSN",
)
MIN_SECRET_LENGTH = 8  # shorter values would also scrub ordinary words

_PATTERNS = [
    # ?key=..., &api_key=..., token=... in a URL or a query-like string
    (re.compile(r"(?i)([?&;\s](?:api[_-]?key|key|token|access_token|apikey|secret)=)[^&\s'\"<>]+"), r"\1" + REDACTED),
    # Authorization: Bearer xxx
    (re.compile(r"(?i)\b(bearer\s+)[A-Za-z0-9._~+/=-]{8,}"), r"\1" + REDACTED),
    # JSON Web Tokens
    (re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"), REDACTED),
    # Google API keys (classic and the newer "AQ." form), OpenAI-style and Supabase secret keys
    (re.compile(r"\bAIza[0-9A-Za-z_-]{20,}"), REDACTED),
    (re.compile(r"\bAQ\.[0-9A-Za-z_-]{20,}"), REDACTED),
    (re.compile(r"\bsk-[0-9A-Za-z_-]{20,}"), REDACTED),
    (re.compile(r"\bsb_secret_[0-9A-Za-z_-]{10,}"), REDACTED),
]


def _known_secret_values() -> list[str]:
    values = {os.environ.get(name, "") for name in SECRET_ENV_NAMES}
    return sorted((v for v in values if len(v) >= MIN_SECRET_LENGTH), key=len, reverse=True)


def redact(text) -> str:
    """Returns `text` (any object is converted with str()) with secrets replaced."""
    if text is None:
        return ""
    cleaned = str(text)
    for secret in _known_secret_values():
        cleaned = cleaned.replace(secret, REDACTED)
    for pattern, replacement in _PATTERNS:
        cleaned = pattern.sub(replacement, cleaned)
    return cleaned


def safe_error(exc: BaseException, limit: int = 300) -> str:
    """A short, secret-free description of an exception for storing or showing."""
    return redact(f"{type(exc).__name__}: {exc}")[:limit]
