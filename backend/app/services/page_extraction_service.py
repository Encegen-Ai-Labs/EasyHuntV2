import io
import json
import re
from typing import Any, Dict, List

import fitz  # PyMuPDF
from PIL import Image
from google.genai import types

from app.services.llm_extractor import client_genai, _clean_json_response

# 2026-08-21: replaced the older, narrower verbatim-only prompt with a more
# detailed "forensic extraction" prompt (user-supplied, evaluated against the
# pipeline's requirements before adopting) — still plain-text-only output
# (extract_page_text() below calls response.text.strip(), not JSON) and still
# verbatim/no-hallucination, but now also asks for layout/table preservation
# and explicit bracket-tagging of non-text elements (signatures, stamps,
# checkboxes, handwritten notes). Those tags are intentionally kept in
# document_pages.original_text / extracted["full_text"] for reviewer display,
# but must NOT be sent to the text-only structured-field-extraction call or to
# the translation API, since neither expects inline annotation markup mixed
# into the prose — see strip_annotation_tags() below, used by
# pipeline_service.py and translation_service.py respectively.
PAGE_TRANSCRIPTION_PROMPT = """You are a Forensic Document Extraction Engine transcribing a single page of an Indian property document, which may include handwritten text in Hindi, Marathi, Tamil, Telugu, Kannada, or other Indian regional languages. Your sole task is a lossless, verbatim transcription of this page. Do not act as a conversational assistant.

Transcribe every visible character exactly as it appears, including typos, grammatical errors, and archaic legal phrasing, in the original script. Do not translate. Do not correct spelling or fix formatting. Preserve the spatial layout — keep paragraphs, line breaks, indentation, and column structure intact. Represent any table or grid using markdown tables or aligned text.

Tag non-standard elements in brackets: [Signature: Handwritten], [Stamp: <text on the stamp, e.g. Received 12-Oct>], [Checkbox: Checked] or [Checkbox: Unchecked]. Demarcate handwritten notes, dates, or signatures that appear alongside typed text, e.g. [Handwritten note: "Approved"].

If a word, number, or smudge is entirely illegible due to poor scan quality, write [illegible] at that point rather than guessing — never fill in blanks, complete truncated sentences, or guess missing numbers/dates based on context, and never add legal boilerplate that isn't physically visible on the page.

Return ONLY the transcribed text as plain text. No JSON, no markdown preamble, no summary, no explanation, no "Here is the transcription" — output the raw transcription immediately, nothing else."""

# Matches the bracket-tag vocabulary from PAGE_TRANSCRIPTION_PROMPT above
# ([Signature: ...], [Stamp: ...], [Checkbox: ...], [Handwritten note: ...])
# but deliberately NOT [illegible], which is meaningful inline content (marks
# a gap in the transcription itself) rather than a structural annotation, and
# is unchanged from the prior prompt's behavior.
_ANNOTATION_TAG_RE = re.compile(
    r"\[\s*(?:Signature|Stamp|Checkbox|Handwritten(?:\s+note)?)\s*:[^\]]*\]",
    re.IGNORECASE,
)


def strip_annotation_tags(text: str) -> str:
    """Removes forensic-extraction bracket tags (signature/stamp/checkbox/
    handwritten-note markers) from transcribed text. Used before sending text
    to consumers that expect plain prose — the structured-field-extraction
    LLM call and the translation API — while the tagged version is kept as-is
    for reviewer-facing display (document_pages.original_text, extracted
    full_text). Collapses the whitespace left behind so stripped text doesn't
    end up with stray blank runs."""
    if not text:
        return text
    stripped = _ANNOTATION_TAG_RE.sub("", text)
    # Collapse runs of 3+ blank lines (left behind by a removed tag that had
    # its own line) down to a single blank line; leave single line breaks and
    # normal spacing untouched.
    stripped = re.sub(r"\n[ \t]*\n[ \t]*\n+", "\n\n", stripped)
    return stripped

# Pages are rasterized at this resolution before enhancement/routing — high
# enough to keep handwriting legible without producing unreasonably large images.
RASTER_DPI = 200

PDF_MIME_TYPES = {"application/pdf"}

# A non-PDF image upload has no equivalent to RASTER_DPI's deliberate size
# cap — a modern phone photo can be 4000+px on a side, and (worse) that's
# before enhancement, whose lossless PNG re-encoding of natural photographic
# texture/noise can balloon well past the original upload's size (measured:
# a 2.7MB JPEG came out at 16MB as a plain PNG, 26MB after color-preserving
# cleaning — see image_enhancement.py). That's the payload sent to the VLM;
# a page that large is slow to upload and process regardless of how "clean"
# or legible it actually is — this was the direct cause of 504
# DEADLINE_EXCEEDED on pages with nothing actually wrong with them. Cap to
# roughly the same scale RASTER_DPI already uses for PDF pages (a full
# A4/Letter page comes out ~1650-1700 x 2200-2340px at 200 DPI) — high
# enough to keep handwriting legible (this is the same target this module
# already trusts for that), capped enough to keep payloads sane.
MAX_IMAGE_DIMENSION_PX = 2400

# Per-request timeout for the page-transcription VLM call, in milliseconds.
# Without an explicit timeout the underlying httpx client waits indefinitely
# on a slow/stuck Gemini response — with pages now routed concurrently
# (pipeline_service.py), one hung page could otherwise tie up a worker slot
# forever instead of failing and letting that page fall back visibly.
#
# 45s (this constant's original value) turned out to be too tight and fired
# on legitimate slow-but-fine responses, not just genuinely stuck ones — a
# densely typewritten page pushes PAGE_TRANSCRIPTION_PROMPT's "verbatim,
# every character, preserve layout, tag every stamp/signature/checkbox"
# instructions much harder than a sparse handwritten note does: full-page
# body text means many more output tokens to generate, which takes
# proportionally longer regardless of image size. 2 minutes gives that
# legitimate case room while still bounding a truly hung request.
GEMINI_PAGE_TIMEOUT_MS = 120_000

# The google-genai SDK makes exactly one attempt per call unless told
# otherwise — passing no retry_options isn't "use sensible defaults", it's
# tenacity.stop_after_attempt(1): a single transient 504/503/429 from
# Gemini's own infrastructure (observed directly: a page transcription
# call got an actual "504 Gateway Timeout" HTTP response from Google after
# 48s, well inside GEMINI_PAGE_TIMEOUT_MS above — this is Google's backend
# giving up, not us) permanently fails that page with no second chance.
# 3 attempts, the SDK's own default backoff (1s initial, doubling, capped
# at 60s, jittered) — enough to recover from a momentary blip without
# piling up unbounded retries on top of MAX_CONCURRENT_PAGES_PER_DOCUMENT's
# already-concurrent calls. httpStatusCodes is left at the SDK default
# (408/429/500/502/503/504), which already covers this.
GEMINI_RETRY_OPTIONS = types.HttpRetryOptions(attempts=3)


def extract_page_text(image_bytes: bytes, mime_type: str = "image/png") -> Dict[str, Any]:
    """Transcribes a single page image via the VLM. Called by
    document_router.py when a page is routed to (or falls back to) the VLM —
    narrow prompt, plain text (not JSON), no structured fields, so one page's
    failure can't corrupt another page's result."""
    try:
        response = client_genai.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                PAGE_TRANSCRIPTION_PROMPT
            ],
            config=types.GenerateContentConfig(
                temperature=0.0,
                http_options=types.HttpOptions(
                    timeout=GEMINI_PAGE_TIMEOUT_MS,
                    retry_options=GEMINI_RETRY_OPTIONS,
                ),
            )
        )
        return {"success": True, "text": response.text.strip(), "error": None}
    except Exception as e:
        return {"success": False, "text": None, "error": str(e)}


# Delimiter separating the verbatim transcription from the structured-fields
# JSON block in PAGE_TRANSCRIPTION_AND_EXTRACTION_PROMPT's response — see
# extract_page_text_and_fields for why a delimiter, not one JSON object with
# the transcription as a field: asking a model to emit a whole page's
# multi-paragraph, tag-laden verbatim transcription *as a JSON string value*
# means it also has to get every embedded newline/quote's escaping right, a
# failure mode plain-text output (today's extract_page_text) doesn't have at
# all. Keeping the transcription as plain text and only JSON-encoding the
# short fields block keeps that same reliability while still folding both
# into one call.
FIELDS_DELIMITER = "===FIELDS==="

# Combines PAGE_TRANSCRIPTION_PROMPT's transcription/tagging instructions
# with the same field schema llm_extractor.STRUCTURED_EXTRACTION_FROM_TEXT_PROMPT
# asks for (kept in sync by hand — deliberately not string-spliced from that
# prompt, which has its own preamble not meant for this context) — used by
# document_router.route_and_extract_page's also_extract_fields path (see its
# docstring) to cut a single-page document's two sequential Gemini calls
# (transcribe, then extract-from-transcription) down to one.
PAGE_TRANSCRIPTION_AND_EXTRACTION_PROMPT = f"""{PAGE_TRANSCRIPTION_PROMPT}

After the transcription, on its own line write exactly:
{FIELDS_DELIMITER}

Then, on the lines after that, return ONLY a single valid JSON object (no markdown backticks, no explanation) extracting these fields from what you just transcribed:

{{
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
  "overall_confidence": "high | medium | low",
  "unreadable_sections": "describe which fields, if any, are affected by [illegible] markers in the transcription, else null",
  "chain": [
    {{
      "order": 1,
      "owner": "owner name",
      "date": "YYYY-MM-DD",
      "type": "Sale Deed | Mutation | Gift | Inheritance | other",
      "survey": "survey number"
    }}
  ]
}}

Rules for the JSON:
- If a field is not present or not stated, use null and mark its confidence as low
- Never guess a name, date, or number you are not confident about — mark confidence low instead of inventing a plausible-looking value
- chain array should contain all ownership transfers visible on this page, in chronological order
- If only a year is known for a date, use YYYY-01-01 and note this in unreadable_sections, rather than inventing 00 for missing parts"""


def extract_page_text_and_fields(image_bytes: bytes, mime_type: str = "image/png") -> Dict[str, Any]:
    """Transcribes a page AND extracts structured fields from it in one
    Gemini call, instead of extract_page_text followed by a separate
    llm_extractor.extract_structured_fields_from_text call. Only used for
    single-page documents (see document_router.py's also_extract_fields) —
    a multi-page document's fields need the *whole* merged transcription,
    which isn't available until every page has been transcribed, so there's
    nothing to combine there.

    Returns {success, text, extracted, model_used, error} — "text" matches
    extract_page_text's key, "extracted"/"model_used"/"error" match
    llm_extractor.extract_structured_fields_from_text's, so a caller with a
    single page can use this result in place of *both* calls without
    reshaping it first.
    """
    try:
        response = client_genai.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                PAGE_TRANSCRIPTION_AND_EXTRACTION_PROMPT
            ],
            config=types.GenerateContentConfig(
                temperature=0.0,
                http_options=types.HttpOptions(
                    timeout=GEMINI_PAGE_TIMEOUT_MS,
                    retry_options=GEMINI_RETRY_OPTIONS,
                ),
            )
        )
        raw = response.text
        if FIELDS_DELIMITER not in raw:
            return {
                "success": False, "text": None, "extracted": None,
                "model_used": "gemini-3.5-flash-lite",
                "error": f"Model response missing '{FIELDS_DELIMITER}' delimiter",
            }
        text_part, _, fields_part = raw.partition(FIELDS_DELIMITER)
        extracted = json.loads(_clean_json_response(fields_part))
        return {
            "success": True,
            "text": text_part.strip(),
            "extracted": extracted,
            "model_used": "gemini-3.5-flash-lite",
            "error": None,
        }
    except json.JSONDecodeError:
        return {
            "success": False, "text": None, "extracted": None,
            "model_used": "gemini-3.5-flash-lite",
            "error": "Model returned invalid JSON in the fields block",
        }
    except Exception as e:
        return {"success": False, "text": None, "extracted": None, "model_used": "gemini-3.5-flash-lite", "error": str(e)}


def _cap_image_dimensions(img: Image.Image) -> Image.Image:
    """Downscales an image whose longest side exceeds
    MAX_IMAGE_DIMENSION_PX, preserving aspect ratio; never upscales a
    smaller image — this only ever brings an oversized upload down to the
    same scale a PDF page would already be rasterized at, never blows a
    small one up past its native resolution. LANCZOS is the right choice
    for downscaling specifically (better than the default nearest/bilinear
    at keeping fine detail like thin pen strokes recognizable)."""
    longest_side = max(img.size)
    if longest_side <= MAX_IMAGE_DIMENSION_PX:
        return img
    scale = MAX_IMAGE_DIMENSION_PX / longest_side
    new_size = (round(img.width * scale), round(img.height * scale))
    return img.resize(new_size, Image.LANCZOS)


def _dpi_for_page(page: "fitz.Page") -> int:
    """Picks the rasterization DPI for one PDF page: RASTER_DPI normally, or
    whatever lower DPI keeps the rendered page within MAX_IMAGE_DIMENSION_PX
    on its longest side. Computed up front rather than rendering at the
    fixed DPI and downscaling after — RASTER_DPI assumes a normal A4/Letter
    page, but a PDF's MediaBox can be anything, and an oversized one (a
    large-format/poster-sized page, or a high-res scan embedded on an
    oversized page) renders to a proportionally oversized image at a fixed
    DPI regardless of how reasonable that DPI sounds. Verified against a
    real document that hit this: a 1606x2365pt page (~22x33in, not a normal
    page size) rendered at the fixed 200 DPI came out 4463x6569px — an
    11.9MB PNG that ballooned to 44MB after color-preserving enhancement,
    consistently too much for Gemini's vision endpoint to finish before
    timing out (504, on every one of 3 retries — not a transient blip, the
    payload itself was the problem). Normal-sized pages are unaffected:
    this only ever lowers the DPI below RASTER_DPI, never raises it."""
    longest_side_in = max(page.rect.width, page.rect.height) / 72.0
    if longest_side_in <= 0:
        return RASTER_DPI
    capped_dpi = MAX_IMAGE_DIMENSION_PX / longest_side_in
    # get_pixmap requires an int DPI (fz_pixmap_xres_set rejects a float).
    # Floor rather than round so a page right at the boundary still lands
    # at or under MAX_IMAGE_DIMENSION_PX, never a pixel or two over it.
    return int(min(RASTER_DPI, capped_dpi))


def rasterize_pages(file_bytes: bytes, mime_type: str) -> List[bytes]:
    """Splits a document into one PNG image per page.

    A non-PDF upload (any image format) is treated as a single page, normalized
    to PNG so every downstream step (enhancement, OCR, VLM) always deals with
    one consistent format regardless of what was actually uploaded. A PDF is
    rasterized page-by-page via PyMuPDF — every page, always, since each page
    is now independently routed to OCR or the VLM rather than the whole
    document being read in one vision call.
    """
    if mime_type not in PDF_MIME_TYPES:
        with Image.open(io.BytesIO(file_bytes)) as img:
            resized = _cap_image_dimensions(img.convert("RGB"))
            buf = io.BytesIO()
            resized.save(buf, format="PNG")
            return [buf.getvalue()]

    pdf = fitz.open(stream=file_bytes, filetype="pdf")
    try:
        pages: List[bytes] = []
        for index in range(pdf.page_count):
            page = pdf[index]
            pixmap = page.get_pixmap(dpi=_dpi_for_page(page))
            pages.append(pixmap.tobytes("png"))
        return pages
    finally:
        pdf.close()


def download_and_rasterize(file_url: str, mime_type: str) -> List[bytes]:
    """Downloads the document from its signed URL and splits it into page
    images. Raises on failure — unlike the old page-extraction step this
    replaces, rasterization happens before the routed per-page extraction
    loop even starts, so there's nothing partial to protect by swallowing the
    error here; the caller (pipeline_service.py) handles it the same way a
    whole-document extraction failure has always been handled."""
    import httpx
    with httpx.Client() as client:
        response = client.get(file_url)
        response.raise_for_status()
    return rasterize_pages(response.content, mime_type)
