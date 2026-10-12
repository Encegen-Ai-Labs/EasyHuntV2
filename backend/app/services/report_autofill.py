"""Fills a bank template's fields from the approved documents.

One Gemini call reads the approved documents (their extracted fields and page
text) and answers only the template fields that documents can actually
answer. Legal-judgement fields (review_level "must_confirm") and the
advocate's own profile fields are never sent, so they cannot be filled here.

The model is told to leave a field null unless a document states it; this
module then drops anything that is not a known field, a choice that is not one
of the allowed options, or an empty value. The lawyer still checks every
filled field on screen.
"""
import json
from typing import Any, Callable, Dict, List, Optional

from google.genai import types

from app.core.logging import logger
from app.services.llm_extractor import GEMINI_MODEL, _clean_json_response, client_genai
from app.services.llm_usage import generate_tracked

AUTOFILL_TIMEOUT_MS = 120_000
MAX_DOCUMENT_CHARS = 60_000  # across all documents; keeps one call affordable
MAX_TEXT_PER_DOCUMENT = 12_000

AUTOFILL_SOURCES = {"extracted", "case_intake", "search_office"}
# "Nothing needed" and similar are conclusions, not facts a document states.
NON_ANSWERS = {"nil", "n/a", "na", "not applicable", "none", "-", "--", "not available", "not stated", "unknown"}


def eligible_fields(manifest_fields: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """The template fields the documents may answer: facts, not judgements."""
    eligible = []
    for spec in manifest_fields:
        if spec.get("review_level") == "must_confirm" or spec.get("source") == "profile":
            continue
        if spec.get("source") in AUTOFILL_SOURCES or (spec.get("source") == "drafted" and spec.get("review_level") == "glance"):
            eligible.append(spec)
    return eligible


def build_prompt(fields: List[Dict[str, Any]], loops: List[Dict[str, Any]], documents: List[Dict[str, Any]]) -> str:
    field_lines = []
    for spec in fields:
        line = f'- "{spec["name"]}" ({spec.get("type", "text")}): {spec.get("description", "")}'
        if spec.get("options"):
            line += f' Allowed values: {json.dumps(spec["options"], ensure_ascii=False)}'
        field_lines.append(line)

    loop_lines = []
    for spec in loops:
        item_fields = list(spec.get("item_fields", []))
        nested = list((spec.get("nested_lists") or {}).keys())
        shape = {name: "text" for name in item_fields}
        shape.update({name: ["text"] for name in nested})
        loop_lines.append(f'- "{spec["name"]}": {spec.get("description", "")} One object per entry: {json.dumps(shape)}')

    budget = MAX_DOCUMENT_CHARS
    document_blocks = []
    for document in documents:
        text = (document.get("text") or "")[:MAX_TEXT_PER_DOCUMENT][:max(budget, 0)]
        budget -= len(text)
        document_blocks.append(
            f'=== Document: {document["name"]} ===\n'
            f'Extracted fields (checked by the lawyer): {json.dumps(document.get("fields") or {}, ensure_ascii=False)}\n'
            f"Text:\n{text}"
        )

    return (
        "You help an Indian property lawyer fill in a bank's title scrutiny report. Below are the documents "
        "the lawyer has approved, then the report fields to fill.\n\n"
        "Rules:\n"
        "- Fill a field ONLY if an approved document clearly states it. Otherwise use null. Never guess, never infer "
        "a legal conclusion, never write that a title is clear, marketable or free of encumbrances.\n"
        "- Write values in English. Transliterate Marathi/Hindi names and places into English letters; keep numbers "
        "exactly as written (survey and gat numbers, registration numbers, areas with units).\n"
        "- Dates as DD/MM/YYYY.\n"
        "- Never answer Nil, N/A, None or Not applicable: if a document does not state it, use null.\n"
        "- For a field with allowed values, answer with exactly one of them, or null.\n"
        "- For a list, return an array of objects, or an empty array if the documents do not support any entry.\n"
        "- Return ONLY one JSON object: {\"fields\": {name: value-or-null, ...}, \"loops\": {name: [entry, ...], ...}}. "
        "No explanation.\n\n"
        "REPORT FIELDS:\n" + "\n".join(field_lines) + "\n\n"
        "REPORT LISTS:\n" + ("\n".join(loop_lines) or "(none)") + "\n\n"
        "DOCUMENTS:\n" + "\n\n".join(document_blocks)
    )


def _gemini_generate(prompt: str) -> str:
    response = generate_tracked("report_autofill", 
        model=GEMINI_MODEL,
        contents=[prompt],
        config=types.GenerateContentConfig(
            temperature=0.0,
            response_mime_type="application/json",
            http_options=types.HttpOptions(
                timeout=AUTOFILL_TIMEOUT_MS,
                retry_options=types.HttpRetryOptions(attempts=3),
            ),
        ),
    )
    return response.text


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, dict)):
        return ""
    return str(value).strip()


def clean_answer(
    raw: Dict[str, Any], fields: List[Dict[str, Any]], loops: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Keeps only usable answers: known field names, non-empty text, a choice
    that is one of the allowed options, and list entries shaped like the
    template's own."""
    answered_fields: Dict[str, str] = {}
    raw_fields = raw.get("fields") if isinstance(raw.get("fields"), dict) else {}
    for spec in fields:
        value = _text(raw_fields.get(spec["name"]))
        if not value or value.lower() in NON_ANSWERS:
            continue
        if spec.get("options") and value not in [str(o) for o in spec["options"]]:
            continue
        answered_fields[spec["name"]] = value

    answered_loops: Dict[str, List[Dict[str, Any]]] = {}
    raw_loops = raw.get("loops") if isinstance(raw.get("loops"), dict) else {}
    for spec in loops:
        entries = raw_loops.get(spec["name"])
        if not isinstance(entries, list):
            continue
        nested = set((spec.get("nested_lists") or {}).keys())
        rows = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            row: Dict[str, Any] = {name: _text(entry.get(name)) for name in spec.get("item_fields", [])}
            for name in nested:
                items = entry.get(name)
                row[name] = [_text(i) for i in items if _text(i)] if isinstance(items, list) else []
            if any(row.values()):
                rows.append(row)
        if rows:
            answered_loops[spec["name"]] = rows

    return {"fields": answered_fields, "loops": answered_loops}


def autofill(
    manifest: Dict[str, Any],
    documents: List[Dict[str, Any]],
    generate: Optional[Callable[[str], str]] = None,
) -> Dict[str, Any]:
    """Returns {"fields": {name: text}, "loops": {name: [row, ...]}}. Raises on
    a model or parsing failure; the caller decides what to do without it."""
    fields = eligible_fields(manifest.get("fields", []))
    loops = [loop for loop in manifest.get("loops", []) if loop.get("review_level") != "must_confirm"]
    if not documents or (not fields and not loops):
        return {"fields": {}, "loops": {}}

    prompt = build_prompt(fields, loops, documents)
    raw_text = (generate or _gemini_generate)(prompt)
    try:
        raw = json.loads(_clean_json_response(raw_text))
    except json.JSONDecodeError:
        logger.error("report.autofill_bad_json | length=%s", len(raw_text or ""))
        raise
    if not isinstance(raw, dict):
        raise ValueError("autofill answer was not a JSON object")
    return clean_answer(raw, fields, loops)
