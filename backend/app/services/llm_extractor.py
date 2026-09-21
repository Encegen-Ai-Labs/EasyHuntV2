from google import genai
from google.genai import types
import json
import os
import tempfile
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()

client_genai = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Per-request timeout for structured-field-extraction/whole-document Gemini
# calls, in milliseconds — see page_extraction_service.GEMINI_PAGE_TIMEOUT_MS
# for why an explicit timeout matters (no timeout means an indefinite hang on
# a stuck response, which would otherwise look identical to "the pipeline
# stopped" with no way to tell the two apart) and why 120s, not something
# tighter: extract_structured_fields_from_text's input is the whole
# document's already-merged per-page transcription, which for a multi-page
# typewritten document can be a lot of text — a larger input context takes
# proportionally longer to process even though the JSON it returns is short.
GEMINI_EXTRACTION_TIMEOUT_MS = 120_000

# See page_extraction_service.GEMINI_RETRY_OPTIONS for why this exists at
# all: the SDK makes exactly one attempt per call unless retry_options is
# set, so a single transient 504/503/429 from Gemini's own infrastructure
# permanently fails the whole document with no second chance (observed
# directly: a structured-extraction call — small input, the page
# transcription it was reading had already failed — still took 119.5s and
# came back with an actual "504 Gateway Timeout" from Google).
GEMINI_RETRY_OPTIONS = types.HttpRetryOptions(attempts=3)

EXTRACTION_PROMPT = """You are an expert at reading Indian property documents including handwritten text in Hindi, Marathi, Tamil, Telugu, Kannada and other Indian regional languages.

First, transcribe the ENTIRE document text verbatim, exactly as written, in its original script. Do not translate. Do not correct spelling. If a word or character is genuinely illegible, write [illegible] at that point rather than guessing.

Then extract the following fields and return ONLY a valid JSON object. No explanation, no preamble, no markdown backticks, just raw JSON.

{
  "full_text": "complete verbatim transcription of the entire document in original script and language, preserving line breaks where meaningful, using [illegible] for unclear portions",
  "document_type": "sale_deed | mutation_record | tax_receipt | encumbrance_certificate | partition_deed | gift_deed | other",
  "owner_name": "full name of current owner or null",
  "owner_name_confidence": "high | medium | low",
  "previous_owner_name": "full name of previous owner if present, else null",
  "previous_owner_name_confidence": "high | medium | low",
  "survey_number": "property survey or plot number or null",
  "survey_number_confidence": "high | medium | low",
  "transaction_date": "date in YYYY-MM-DD format or null",
  "transaction_date_confidence": "high | medium | low",
  "transaction_type": "sale | inheritance | gift | partition | other",
  "property_location": "address or location description or null",
  "property_boundaries": "boundary description or null",
  "area": "property area with unit or null",
  "registration_number": "document registration number or null",
  "language_detected": "primary language of the document",
  "has_handwritten_content": true or false,
  "overall_confidence": "high | medium | low",
  "unreadable_sections": "describe unclear sections or null",
  "chain": [
    {
      "order": 1,
      "owner": "owner name",
      "date": "YYYY-MM-DD",
      "type": "Sale Deed | Mutation | Gift | Inheritance | other",
      "survey": "survey number"
    }
  ]
}

Rules:
- Return ONLY the JSON object, nothing else
- No markdown backticks
- No explanation before or after
- If a field is not present or not readable use null, and mark its confidence as low
- Never guess a name, date, or number you are not confident about — mark confidence low instead of inventing a plausible-looking value
- has_handwritten_content: true if ANY part of the document contains handwritten text, even a printed form with handwritten fields filled in. false only if the entire document is printed, typed, or typewritten. Be conservative — if in doubt, mark it true
- chain array should contain all ownership transfers visible in the document in chronological order
- If only a year is known for a date (no specific day/month), use YYYY-01-01 and note this in unreadable_sections, rather than inventing 00 for missing parts
- full_text must be the actual transcription, not a summary or paraphrase"""


# Used by the OCR/VLM-routed pipeline (document_router.py + pipeline_service.py):
# by the time this runs, the document has already been transcribed page-by-page
# (each page independently routed to Tesseract or Gemini's vision call — see
# document_router.py), so this call only has to pull structured fields out of
# already-known text, not read an image. Deliberately does NOT ask for
# full_text (the caller already has the routed transcription and just merges
# it in) or has_handwritten_content (that's a visual property the router's
# per-page OCR analysis already determined more reliably than a text-only
# model guessing from transcribed words could).
STRUCTURED_EXTRACTION_FROM_TEXT_PROMPT = """You are an expert at reading Indian property documents. Below is the verbatim transcription of a document (it may be in Hindi, Marathi, Tamil, Telugu, Kannada, English, or another Indian regional language; [illegible] marks portions the transcriber could not read).

Extract the following fields from the transcription and return ONLY a valid JSON object. No explanation, no preamble, no markdown backticks, just raw JSON.

{
  "document_type": "sale_deed | mutation_record | tax_receipt | encumbrance_certificate | partition_deed | gift_deed | other",
  "owner_name": "full name of current owner or null",
  "owner_name_confidence": "high | medium | low",
  "previous_owner_name": "full name of previous owner if present, else null",
  "previous_owner_name_confidence": "high | medium | low",
  "survey_number": "property survey or plot number or null",
  "survey_number_confidence": "high | medium | low",
  "transaction_date": "date in YYYY-MM-DD format or null",
  "transaction_date_confidence": "high | medium | low",
  "transaction_type": "sale | inheritance | gift | partition | other",
  "property_location": "address or location description or null",
  "property_boundaries": "boundary description or null",
  "area": "property area with unit or null",
  "registration_number": "document registration number or null",
  "language_detected": "primary language of the document",
  "overall_confidence": "high | medium | low — your confidence extracting these fields from the given text (not the original scan's image quality, which you cannot see)",
  "unreadable_sections": "describe which fields, if any, are affected by [illegible] markers in the text, else null",
  "chain": [
    {
      "order": 1,
      "owner": "owner name",
      "date": "YYYY-MM-DD",
      "type": "Sale Deed | Mutation | Gift | Inheritance | other",
      "survey": "survey number"
    }
  ]
}

Rules:
- Return ONLY the JSON object, nothing else
- No markdown backticks, no explanation before or after
- If a field is not present or not stated in the text, use null and mark its confidence as low
- Never guess a name, date, or number you are not confident about — mark confidence low instead of inventing a plausible-looking value
- chain array should contain all ownership transfers visible in the text, in chronological order
- If only a year is known for a date (no specific day/month), use YYYY-01-01 and note this in unreadable_sections, rather than inventing 00 for missing parts"""


def extract_structured_fields_from_text(text: str) -> Dict[str, Any]:
    """Text-mode counterpart to extract_from_image_path — same field schema
    minus full_text/has_handwritten_content (see prompt comment above for why),
    both merged back in by the caller (pipeline_service.py) since it already
    has the routed transcription and the router's own handwriting signal."""
    raw_output = None
    try:
        response = client_genai.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=[STRUCTURED_EXTRACTION_FROM_TEXT_PROMPT, text],
            config=types.GenerateContentConfig(
                temperature=0.0,
                http_options=types.HttpOptions(
                    timeout=GEMINI_EXTRACTION_TIMEOUT_MS,
                    retry_options=GEMINI_RETRY_OPTIONS,
                ),
            ),
        )
        raw_output = response.text
        cleaned = _clean_json_response(raw_output)
        extracted = json.loads(cleaned)
        return {
            "success": True,
            "raw_output": raw_output,
            "extracted": extracted,
            "model_used": "gemini-3.5-flash-lite",
            "error": None,
        }
    except json.JSONDecodeError:
        return {
            "success": False,
            "raw_output": raw_output,
            "extracted": None,
            "model_used": "gemini-3.5-flash-lite",
            "error": "Model returned invalid JSON",
        }
    except Exception as e:
        return {
            "success": False,
            "raw_output": None,
            "extracted": None,
            "model_used": "gemini-3.5-flash-lite",
            "error": str(e),
        }


def _clean_json_response(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return raw.strip()


def _get_mime_type(file_path: str) -> str:
    ext = file_path.lower().rsplit(".", 1)[-1] if "." in file_path else ""
    mime_map = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
        "pdf": "application/pdf"
    }
    return mime_map.get(ext, "image/jpeg")


# Reverse of _get_mime_type's map — used to pick a temp-file suffix that
# actually matches downloaded bytes (see extract_from_supabase_url).
_EXT_BY_MIME = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "application/pdf": ".pdf",
}


def extract_from_image_path(image_path: str, mime_type: str | None = None) -> Dict[str, Any]:
    raw_output = None
    try:
        with open(image_path, "rb") as f:
            file_bytes = f.read()

        # Caller-supplied mime_type (the document's real, known type) always
        # wins over guessing from the temp file's extension — the extension
        # alone is only a reasonable guess when nothing better is known.
        mime_type = mime_type or _get_mime_type(image_path)

        response = client_genai.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=[
                types.Part.from_bytes(
                    data=file_bytes,
                    mime_type=mime_type
                ),
                EXTRACTION_PROMPT
            ],
            config=types.GenerateContentConfig(
                temperature=0.0,
                http_options=types.HttpOptions(
                    timeout=GEMINI_EXTRACTION_TIMEOUT_MS,
                    retry_options=GEMINI_RETRY_OPTIONS,
                ),
            )
        )

        raw_output = response.text
        cleaned = _clean_json_response(raw_output)
        extracted = json.loads(cleaned)

        return {
            "success": True,
            "raw_output": raw_output,
            "extracted": extracted,
            "model_used": "gemini-3.5-flash-lite",
            "error": None
        }

    except json.JSONDecodeError:
        return {
            "success": False,
            "raw_output": raw_output,
            "extracted": None,
            "model_used": "gemini-3.5-flash-lite",
            "error": "Model returned invalid JSON"
        }
    except Exception as e:
        return {
            "success": False,
            "raw_output": None,
            "extracted": None,
            "model_used": "gemini-3.5-flash-lite",
            "error": str(e)
        }


def extract_from_supabase_url(file_url: str, mime_type: str | None = None) -> Dict[str, Any]:
    try:
        import httpx
        with httpx.Client() as client:
            response = client.get(file_url)
            response.raise_for_status()

        # The temp file's suffix must actually match the downloaded bytes —
        # previously this always used ".jpg" regardless of the real file type,
        # so a PDF's raw bytes would get labeled image/jpeg when sent to
        # Gemini, which Gemini sometimes rejected outright (400 INVALID_ARGUMENT
        # "Unable to process input image") and sometimes silently tolerated,
        # depending on how forgiving its own content-sniffing happened to be.
        suffix = _EXT_BY_MIME.get(mime_type, ".jpg") if mime_type else ".jpg"

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=suffix
        ) as tmp:
            tmp.write(response.content)
            tmp_path = tmp.name

        result = extract_from_image_path(tmp_path, mime_type=mime_type)
        os.unlink(tmp_path)
        return result

    except Exception as e:
        return {
            "success": False,
            "raw_output": None,
            "extracted": None,
            "model_used": "gemini-3.5-flash-lite",
            "error": str(e)
        }
