import os
import time
from typing import Any, Dict, List

import httpx
from dotenv import load_dotenv

from app.core.config import settings
from app.core.logging import logger
from app.core.redaction import redact, safe_error
from app.services.llm_usage import TRANSLATE_GOOGLE, LlmCall, generate_tracked
from app.services.page_extraction_service import strip_annotation_tags
from app.services.text_cleanup import clean_page_text

load_dotenv()

# Two ways to translate, behind translate_to_english() / translate_pages(), the
# only functions the rest of the app calls:
#
# - Google Cloud Translation v2 ("Basic"): cheap, needs a Cloud Translation API
#   key. Note that not every Google key works here: a key that is not enabled
#   for the Cloud Translation API (for example a Gemini-only or Vertex "express"
#   key) is answered with "API keys are not supported by this API".
# - Gemini: the model the app already uses for extraction. Used when Google
#   Translation is not configured or rejects the key (TRANSLATION_PROVIDER=auto),
#   so translation keeps working with the one key every install has.
#
# Tried a self-hosted AI4Bharat IndicTrans2 model on 2026-08-20 and reverted the
# same day: ~2GB of dependencies, CPU-only inference, and a gated model repo.
GOOGLE_TRANSLATE_API_KEY = os.getenv("GOOGLE_TRANSLATE_API_KEY")
GOOGLE_TRANSLATE_URL = "https://translation.googleapis.com/language/translate/v2"
GOOGLE_AUTH_STATUSES = {400, 401, 403}
GOOGLE_RETRY_AFTER_SECONDS = 600
HTTP_TIMEOUT_SECONDS = 30

GEMINI_TRANSLATE_PROMPT = (
    "Translate the text below into English. It comes from an Indian property document and may be in Marathi, "
    "Hindi or another Indian language. Keep personal names and place names as transliterated proper nouns. "
    "Keep numbers, dates, survey and registration numbers, and punctuation exactly as written. Keep line breaks "
    "and any markdown tables. Return only the translation, with no explanation.\n\nTEXT:\n"
)

_google_disabled_until = 0.0


def _failure(message: str, *, auth_failed: bool = False, provider: str) -> Dict[str, Any]:
    return {"success": False, "translated_text": None, "error": message, "auth_failed": auth_failed, "provider": provider}


def _translate_google(text: str) -> Dict[str, Any]:
    key = GOOGLE_TRANSLATE_API_KEY
    if not key:
        return _failure("GOOGLE_TRANSLATE_API_KEY is not configured", auth_failed=True, provider="google")

    try:
        with LlmCall(TRANSLATE_GOOGLE, "google-translate-v2", chars_in=len(text)):
            with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS) as client:
                # The key goes in a header, not the URL: an httpx error message
                # contains the full URL, and a key in it would be logged, stored
                # and shown on screen.
                response = client.post(
                    GOOGLE_TRANSLATE_URL,
                    headers={"x-goog-api-key": key},
                    json={"q": text, "target": "en", "format": "text"},
                )
                response.raise_for_status()
                data = response.json()
        translated = clean_page_text(data["data"]["translations"][0]["translatedText"])
        return {"success": True, "translated_text": translated, "error": None, "provider": "google"}
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        # Google's own message is the useful part ("API keys are not supported
        # by this API..."); the exception text is not, because it carries the URL.
        try:
            detail = redact(e.response.json()["error"]["message"])
        except Exception:
            detail = redact(getattr(e.response, "text", "") or "")
        message = f"Google Translation error {status}" + (f": {detail[:240]}" if detail else "")
        return _failure(message, auth_failed=status in GOOGLE_AUTH_STATUSES, provider="google")
    except Exception as e:
        return _failure(safe_error(e), provider="google")


def _translate_gemini(text: str) -> Dict[str, Any]:
    try:
        from google.genai import types

        from app.services.llm_extractor import GEMINI_MODEL

        response = generate_tracked(
            "translation",
            model=GEMINI_MODEL,
            contents=[GEMINI_TRANSLATE_PROMPT + text],
            config=types.GenerateContentConfig(
                temperature=0.0,
                http_options=types.HttpOptions(timeout=60_000, retry_options=types.HttpRetryOptions(attempts=3)),
            ),
        )
        translated = clean_page_text((response.text or "").strip())
        return {"success": True, "translated_text": translated, "error": None, "provider": "gemini"}
    except Exception as e:
        return _failure(safe_error(e), provider="gemini")


def translate_to_english(text: str) -> Dict[str, Any]:
    """Translates text to English. Source language is left to the provider to
    auto-detect rather than mapped from our free-text language_detected field."""
    global _google_disabled_until
    if not text or not text.strip():
        return {"success": True, "translated_text": "", "error": None}

    mode = (settings.TRANSLATION_PROVIDER or "auto").lower()
    if mode == "gemini":
        return _translate_gemini(text)

    if mode == "google" or time.monotonic() >= _google_disabled_until:
        result = _translate_google(text)
        if result["success"] or mode == "google" or not result.get("auth_failed"):
            return result
        # Google Translation is unusable with this key; use Gemini for a while
        # instead of failing every page and retrying the bad key every time.
        _google_disabled_until = time.monotonic() + GOOGLE_RETRY_AFTER_SECONDS
        logger.warning("translation.google_unavailable | using=gemini retry_in_seconds=%s reason=%s",
                       GOOGLE_RETRY_AFTER_SECONDS, result["error"][:160])
    return _translate_gemini(text)


def translate_pages(pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Adds "english_text" to each {"page_number":.., "original_text":..} row.
    Runs sequentially so one document never opens many external calls at once
    (PipelineService caps concurrent documents at 3). One page's failure doesn't
    block the rest; its english_text becomes a short, secret-free marker."""
    translated_pages: List[Dict[str, Any]] = []
    for page in pages:
        # The forensic-extraction tags ([Signature: ...], [Stamp: ...]) are
        # reviewer-display annotations, not prose; only the copy sent to the
        # translator is cleaned, the stored original_text is untouched.
        result = translate_to_english(strip_annotation_tags(page["original_text"]))
        english_text = (
            result["translated_text"]
            if result["success"]
            else f"[translation failed: {redact(result['error'])[:200]}]"
        )
        translated_pages.append({**page, "english_text": english_text})
    return translated_pages
