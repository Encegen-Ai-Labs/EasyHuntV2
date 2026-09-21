import os
from typing import Any, Dict, List

import httpx
from dotenv import load_dotenv

from app.services.page_extraction_service import strip_annotation_tags

load_dotenv()

# Deliberately a separate, cheap/free-tier provider from the paid Gemini model used
# for extraction — translating every page through Gemini would multiply the paid
# per-call cost for no extraction benefit, so this never routes through it.
# Google Cloud Translation API v2 ("Basic") only needs an API key (no service
# account / GCP project wiring like v3 "Advanced" requires), which matches "free
# tier, minimal infra" from the product decision. Kept behind translate_to_english()
# / translate_pages() as the only functions the rest of the app calls, so swapping
# providers later only touches this file.
#
# Tried swapping this to a locally-hosted AI4Bharat IndicTrans2 model
# (2026-08-20) to avoid Google's per-character cost past its free tier —
# reverted the same day. It added ~1.3GB of dependencies (torch, transformers,
# pandas/sphinx pulled in transitively) plus another ~0.5-0.9GB for the model
# weights, needed CPU inference (multi-second per page, no GPU assumed), and
# the model repo turned out to be gated on HuggingFace (requires an account +
# accepted terms + access token before it will even download) — too much
# weight and setup friction for a feature that isn't this project's core
# purpose. If translation quality ever becomes a real problem with Google
# Translate, revisit as a single shared self-hosted service (not baked into
# every local dev install) rather than in-process.
GOOGLE_TRANSLATE_API_KEY = os.getenv("GOOGLE_TRANSLATE_API_KEY")
GOOGLE_TRANSLATE_URL = "https://translation.googleapis.com/language/translate/v2"


def translate_to_english(text: str) -> Dict[str, Any]:
    """Translates text to English. Source language is left for the API to
    auto-detect rather than mapped from our free-text language_detected field
    (e.g. "Hindi") into an ISO code — auto-detect is the standard approach for the
    v2 Basic API and avoids a fragile language-name-to-code mapping."""
    if not text or not text.strip():
        return {"success": True, "translated_text": "", "error": None}

    if not GOOGLE_TRANSLATE_API_KEY:
        return {"success": False, "translated_text": None, "error": "GOOGLE_TRANSLATE_API_KEY is not configured"}

    try:
        with httpx.Client() as client:
            response = client.post(
                GOOGLE_TRANSLATE_URL,
                params={"key": GOOGLE_TRANSLATE_API_KEY},
                json={
                    "q": text,
                    "target": "en",
                    "format": "text",
                },
            )
            response.raise_for_status()
            data = response.json()

        translated = data["data"]["translations"][0]["translatedText"]
        return {"success": True, "translated_text": translated, "error": None}
    except httpx.HTTPStatusError as e:
        # Google's error body (e.g. {"error": {"message": "API key not valid", ...}})
        # is far more actionable than the bare "401 Unauthorized" that str(e) gives —
        # surface it so misconfiguration (missing API enablement, billing, bad key,
        # restricted key, etc.) is diagnosable from this error alone.
        try:
            detail = e.response.json()["error"]["message"]
        except Exception:
            detail = e.response.text or str(e)
        return {"success": False, "translated_text": None, "error": f"{e} — {detail}"}
    except Exception as e:
        return {"success": False, "translated_text": None, "error": str(e)}


def translate_pages(pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Adds "english_text" to each {"page_number":.., "original_text":..} row.
    Runs sequentially, not concurrently — page extraction (page_extraction_service.py)
    already made the same call for the same reason: batch upload's
    PipelineService.execute_batch() caps concurrent *documents* at 3, and adding
    per-page concurrency here would multiply how many external calls run at once
    on top of that, with no corresponding cap. One page's translation failure
    doesn't block the rest, matching the failure-sentinel pattern used for pages
    whose transcription itself failed."""
    translated_pages: List[Dict[str, Any]] = []
    for page in pages:
        # Strip forensic-extraction bracket tags ([Signature: ...], [Stamp:
        # ...], etc. — see page_extraction_service.py) before translating:
        # they're reviewer-display annotations, not document prose, and the
        # translation API has no reason to see or "translate" them. The
        # page's own original_text (stored separately, already persisted)
        # is untouched — only the copy sent to Google Translate is cleaned.
        result = translate_to_english(strip_annotation_tags(page["original_text"]))
        english_text = (
            result["translated_text"]
            if result["success"]
            else f"[translation failed: {result['error']}]"
        )
        translated_pages.append({**page, "english_text": english_text})
    return translated_pages
