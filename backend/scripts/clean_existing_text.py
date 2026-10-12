"""Strip stray `<br>` tags and non-table `|` characters from text already stored.

Usage (from the api container, in /app, or backend/ locally):
    python -m scripts.clean_existing_text            # dry run: counts only, writes nothing
    python -m scripts.clean_existing_text --apply    # write the cleaned text

Covers document_pages.original_text / english_text and the "full_text" field
inside extractions.validated_json_output (the "Full verbatim transcription").
extractions.raw_ocr_text and raw_json_output are the record of what the model
returned, so they are left as they are. Page embeddings are not recomputed:
removing markup does not change what a page is about.

Only rows whose text actually changes are written. Re-running is harmless.
"""
import sys
from typing import Any, Dict, List

from app.services.text_cleanup import clean_page_text

PAGE_FIELDS = ("original_text", "english_text")
PAGE_SIZE = 500


def _fetch_all(client, table: str, columns: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    start = 0
    while True:
        batch = client.table(table).select(columns).range(start, start + PAGE_SIZE - 1).execute().data
        rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            return rows
        start += PAGE_SIZE


def page_updates(row: Dict[str, Any]) -> Dict[str, str]:
    updates: Dict[str, str] = {}
    for field in PAGE_FIELDS:
        value = row.get(field)
        cleaned = clean_page_text(value)
        if value and cleaned != value:
            updates[field] = cleaned
    return updates


def extraction_update(row: Dict[str, Any]) -> Dict[str, Any] | None:
    validated = row.get("validated_json_output")
    if not isinstance(validated, dict) or not validated.get("full_text"):
        return None
    cleaned = clean_page_text(validated["full_text"])
    if cleaned == validated["full_text"]:
        return None
    return {**validated, "full_text": cleaned}


def run(client, apply: bool) -> Dict[str, int]:
    counts = {"pages_changed": 0, "extractions_changed": 0}

    for row in _fetch_all(client, "document_pages", "id,original_text,english_text"):
        updates = page_updates(row)
        if not updates:
            continue
        counts["pages_changed"] += 1
        if apply:
            client.table("document_pages").update(updates).eq("id", row["id"]).execute()

    for row in _fetch_all(client, "extractions", "id,validated_json_output"):
        new_validated = extraction_update(row)
        if new_validated is None:
            continue
        counts["extractions_changed"] += 1
        if apply:
            client.table("extractions").update({"validated_json_output": new_validated}).eq("id", row["id"]).execute()

    return counts


def main() -> int:
    from app.dependencies.db import get_supabase_service_client

    apply = "--apply" in sys.argv[1:]
    counts = run(get_supabase_service_client(), apply)
    verb = "Updated" if apply else "Would update (dry run, nothing written)"
    print(f"{verb}: {counts['pages_changed']} page(s), {counts['extractions_changed']} extraction(s)")
    if not apply:
        print("Re-run with --apply to write the changes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
