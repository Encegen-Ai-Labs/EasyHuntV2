"""Turn approved, lawyer-reviewed documents into evaluation cases.

  python -m eval.export_corrections --document-id <uuid> [--document-id ...]
  python -m eval.export_corrections --all-approved [--split holdout|example] [--dry-run]

Reads extractions / extraction_corrections / documents from Supabase and the
source file from storage, and writes eval_data/cases/<id>/{source.*,
expected.json, meta.json} in the format eval.loader reads. Runs on YOUR
machine with your own credentials (the app's settings); nothing here is run by
the test suite against a real database.

What counts as labelled: a scalar field is labelled only if a human touched it
(an edit/add/clear row, or a `confirm` row written when the document was
approved). A field with no correction row at all goes under `unlabelled`, so
an unreviewed model guess is never mistaken for a correct answer. New cases
default to the holdout split. Existing case folders are never overwritten.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .loader import DOCUMENT_TYPES, SCHEMA_VERSION, default_data_dir
from .scorers import LIST_FIELDS, SCALAR_FIELDS


def _blank_to_none(v: Any) -> Any:
    if isinstance(v, str):
        return v.strip() or None
    return v


def touched_fields(corrections: List[Dict[str, Any]]) -> set:
    out = set()
    for r in corrections:
        path = r.get("field_path", "")
        if path.startswith("page["):
            continue
        out.add(re.split(r"[\[.]", path, maxsplit=1)[0])
    return out


def build_expected(extraction: Dict[str, Any], corrections: List[Dict[str, Any]], labelled_on: str) -> Dict[str, Any]:
    final = extraction.get("validated_json_output") or {}
    touched = touched_fields(corrections)
    fields: Dict[str, Any] = {}
    unlabelled: List[str] = []
    for name in SCALAR_FIELDS:
        if name in touched:
            fields[name] = _blank_to_none(final.get(name))
        else:
            unlabelled.append(name)
    expected: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "labelled_by": "lawyer review (extraction_corrections)",
        "labelled_on": labelled_on,
        "fields": fields,
    }
    if "chain" in touched:
        expected["chain"] = [
            {k: l.get(k) for k in ("order", "owner", "date", "type", "survey") if l.get(k) is not None}
            for l in (final.get("chain") or []) if isinstance(l, dict)
        ]
    else:
        unlabelled.append("chain")
    if "red_flags" in touched:
        expected["red_flags"] = [
            {k: f.get(k) for k in ("type", "source_text") if f.get(k)}
            for f in (final.get("red_flags") or []) if isinstance(f, dict)
        ]
    else:
        unlabelled.append("red_flags")
    expected["unlabelled"] = unlabelled
    return expected


def build_meta(case_id: str, extraction: Dict[str, Any], split: str, pages: Optional[int]) -> Dict[str, Any]:
    final = extraction.get("validated_json_output") or {}
    doc_type = final.get("document_type")
    return {
        "id": case_id,
        "document_type": doc_type if doc_type in DOCUMENT_TYPES else "other",
        "split": split,
        "language": (final.get("language_detected") or "").strip().lower() or None,
        # The extraction only records whether ANY handwriting was seen, not how
        # much, so "partial" is a placeholder: correct it by hand if it matters.
        "handwriting": "partial" if extraction.get("has_handwritten_content") else "none",
        "pages": pages,
        "notes": f"Exported from document {extraction.get('document_id')}; handwriting level is a placeholder.",
    }


def next_case_id(cases_dir: Path, doc_type: str) -> str:
    cases_dir.mkdir(parents=True, exist_ok=True)
    nums = [int(m.group(1)) for d in cases_dir.iterdir() if (m := re.match(r"^(\d+)_", d.name))]
    return f"{(max(nums) + 1 if nums else 1):04d}_{doc_type}"


def eligible(extraction: Dict[str, Any]) -> Tuple[bool, str]:
    if extraction.get("status") != "approved" or not extraction.get("reviewed_at"):
        return False, "not approved by a reviewer"
    return True, ""


def write_case(data_dir: Path, extraction: Dict[str, Any], corrections: List[Dict[str, Any]],
               source_name: str, source_bytes: bytes, split: str, pages: Optional[int], labelled_on: str) -> Path:
    cases_dir = data_dir / "cases"
    meta_probe = build_meta("x", extraction, split, pages)
    case_id = next_case_id(cases_dir, meta_probe["document_type"])
    case_dir = cases_dir / case_id
    case_dir.mkdir(parents=True, exist_ok=False)  # never overwrite
    ext = Path(source_name).suffix.lower() or ".pdf"
    (case_dir / f"source{ext}").write_bytes(source_bytes)
    (case_dir / "meta.json").write_text(
        json.dumps(build_meta(case_id, extraction, split, pages), indent=2, ensure_ascii=False), encoding="utf-8")
    (case_dir / "expected.json").write_text(
        json.dumps(build_expected(extraction, corrections, labelled_on), indent=2, ensure_ascii=False), encoding="utf-8")
    return case_dir


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="eval.export_corrections", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--document-id", action="append", default=[])
    ap.add_argument("--all-approved", action="store_true")
    ap.add_argument("--split", default="holdout", choices=["holdout", "example"])
    ap.add_argument("--data-dir", type=Path, default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    if not args.document_id and not args.all_approved:
        print("give --document-id or --all-approved", file=sys.stderr)
        return 2

    # Lazy: the offline harness must not load the app's settings or connect.
    from datetime import date
    from app.dependencies.db import get_supabase_service_client
    from app.services.doc_service import STORAGE_BUCKET
    client = get_supabase_service_client()

    if args.all_approved:
        rows = client.table("extractions").select("*").eq("status", "approved").execute().data
    else:
        rows = []
        for did in args.document_id:
            rows += client.table("extractions").select("*").eq("document_id", did).execute().data

    data_dir = args.data_dir or default_data_dir()
    done = 0
    for ex in rows:
        ok, why = eligible(ex)
        if not ok:
            print(f"skip {ex.get('document_id')}: {why}", file=sys.stderr)
            continue
        doc = client.table("documents").select("*").eq("id", ex["document_id"]).execute().data
        if not doc:
            print(f"skip {ex['document_id']}: document row is gone", file=sys.stderr)
            continue
        corrections = client.table("extraction_corrections").select("*").eq("extraction_id", ex["id"]).execute().data
        if args.dry_run:
            exp = build_expected(ex, corrections, date.today().isoformat())
            print(f"would export {ex['document_id']}: labelled {sorted(exp['fields'])}, unlabelled {exp['unlabelled']}")
            continue
        blob = client.storage.from_(STORAGE_BUCKET).download(doc[0]["file_path"])
        pages = len(client.table("document_pages").select("page_number").eq("document_id", ex["document_id"]).execute().data) or None
        path = write_case(data_dir, ex, corrections, doc[0]["file_path"], blob, args.split, pages, date.today().isoformat())
        print(f"exported {ex['document_id']} -> {path}")
        done += 1
    print(f"{done} case(s) written to {data_dir / 'cases'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
