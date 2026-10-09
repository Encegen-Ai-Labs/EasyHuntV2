"""Lawyer corrections as an append-only dataset (docs/EXTRACTION_QUALITY.md 4).

Every save from the review screen is diffed against what the model originally
produced (extractions.raw_json_output) and against what was there just before
the save (extractions.validated_json_output). One row per changed field goes
into `extraction_corrections`; approving a document also records a `confirm`
row for each field the lawyer left alone, because confirmed-correct values are
as useful to the dataset as the corrections.

Rows are never updated or deleted by the app. Recording is best effort: the
lawyer's save is never blocked or lost because dataset bookkeeping failed
(e.g. the table has not been created yet); the failure is logged and reported
in the save response.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.logging import logger

TABLE = "extraction_corrections"

SCALAR_FIELDS = (
    "document_type", "owner_name", "previous_owner_name", "survey_number",
    "transaction_date", "transaction_type", "property_location",
    "property_boundaries", "area", "registration_number", "language_detected",
)
LIST_FIELDS = ("chain", "red_flags")
CONFIRMABLE = SCALAR_FIELDS + LIST_FIELDS

# Never diffed: the transcription has its own per-page corrections, and the
# *_confidence keys are model metadata the review screen cannot edit.
SKIP_KEYS = {"full_text"}

REASONS = ("misread", "wrong_field", "hallucinated", "format", "other")

EDIT, CLEAR, ADD, REMOVE, CONFIRM = "edit", "clear", "add", "remove", "confirm"


def _canon(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, str):
        v = v.strip()
        return v or None
    return v


def _same(a: Any, b: Any) -> bool:
    a, b = _canon(a), _canon(b)
    if a == b:
        return True
    if isinstance(a, (list, dict)) or isinstance(b, (list, dict)) or a is None or b is None:
        return False
    # The review form hands every edited value back as a string, so a boolean
    # or number that was not touched must not look edited.
    return str(a).strip().lower() == str(b).strip().lower()


def _row(path: str, change: str, original: Any, previous: Any, corrected: Any) -> Dict[str, Any]:
    return {"field_path": path, "change_type": change,
            "original_value": original, "previous_value": previous, "corrected_value": corrected}


def _diff_value(path: str, original: Any, before: Any, after: Any, out: List[Dict[str, Any]]) -> None:
    if _same(before, after):
        return
    if isinstance(before, list) or isinstance(after, list):
        b_list = before if isinstance(before, list) else []
        a_list = after if isinstance(after, list) else []
        o_list = original if isinstance(original, list) else []
        for i in range(max(len(b_list), len(a_list))):
            b = b_list[i] if i < len(b_list) else None
            a = a_list[i] if i < len(a_list) else None
            o = o_list[i] if i < len(o_list) else None
            p = f"{path}[{i}]"
            if b is None:
                out.append(_row(p, ADD, o, None, a))
            elif a is None:
                out.append(_row(p, REMOVE, o, b, None))
            elif isinstance(b, dict) and isinstance(a, dict):
                for k in sorted(set(b) | set(a)):
                    _diff_value(f"{p}.{k}", (o or {}).get(k) if isinstance(o, dict) else None, b.get(k), a.get(k), out)
            else:
                _diff_value(p, o, b, a, out)
        return
    change = ADD if _canon(before) is None else CLEAR if _canon(after) is None else EDIT
    out.append(_row(path, change, original, before, after))


def diff_extraction(original: Dict[str, Any], before: Dict[str, Any], after: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Changed fields between the validated output before this save and the
    submitted one, each carrying the model's original value for context."""
    original, before, after = original or {}, before or {}, after or {}
    out: List[Dict[str, Any]] = []
    for key in sorted(set(before) | set(after)):
        if key in SKIP_KEYS or key.endswith("_confidence"):
            continue
        _diff_value(key, original.get(key), before.get(key), after.get(key), out)
    return out


def top_level(path: str) -> str:
    return path.split("[", 1)[0].split(".", 1)[0]


def confirm_rows(original: Dict[str, Any], before: Dict[str, Any], after: Dict[str, Any],
                 changed: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """`confirm` rows for the fields this save did not change."""
    touched = {top_level(r["field_path"]) for r in changed}
    return [
        _row(f, CONFIRM, (original or {}).get(f), (before or {}).get(f), (after or {}).get(f))
        for f in CONFIRMABLE if f not in touched and f in (after or {})
    ]


class CorrectionRecorder:
    """Writes correction rows. `repo` is a BaseRepository."""

    def __init__(self, repo: Any):
        self.repo = repo

    def next_revision(self, extraction_id: str) -> int:
        rows = self.repo.select(TABLE, {"extraction_id": extraction_id})
        return max((int(r.get("revision") or 0) for r in rows), default=0) + 1

    def record_review(
        self, *, extraction: Dict[str, Any], document: Dict[str, Any], reviewer_id: str,
        after: Dict[str, Any], approved: bool, reasons: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Diffs and records one review save. `extraction` is the row as it was
        BEFORE this save. Returns {"recorded": bool, "count": int}."""
        try:
            original = extraction.get("raw_json_output") or {}
            before = extraction.get("validated_json_output") or {}
            rows = diff_extraction(original, before, after)
            if approved:
                rows += confirm_rows(original, before, after, rows)
            if not rows:
                return {"recorded": True, "count": 0}
            revision = self.next_revision(extraction["id"])
            reasons = reasons or {}
            for r in rows:
                top = top_level(r["field_path"])
                reason = reasons.get(r["field_path"]) or reasons.get(top)
                r.update({
                    "extraction_id": extraction["id"],
                    "document_id": document["id"],
                    "case_id": document.get("case_id"),
                    "revision": revision,
                    "corrected_by": reviewer_id,
                    "reason": reason if reason in REASONS else None,
                    "model_used": extraction.get("model_used"),
                    "handwriting": bool(extraction.get("has_handwritten_content")),
                    "model_confidence": original.get(f"{top}_confidence"),
                })
            self.repo.bulk_insert(TABLE, rows)
            return {"recorded": True, "count": len(rows)}
        except Exception as e:
            logger.error(
                "corrections.record_failed | document_id=%s error=%s | the review itself was saved",
                document.get("id"), e,
            )
            return {"recorded": False, "count": 0}

    def record_page_text(
        self, *, document: Dict[str, Any], extraction_id: Optional[str], reviewer_id: str,
        page_number: int, column: str, previous: Optional[str], corrected: Optional[str],
    ) -> bool:
        """A reviewer's edit of a page's original_text / english_text."""
        if _same(previous, corrected):
            return True
        try:
            key = f"page[{page_number}].{column}"
            revision = 1
            if extraction_id:
                revision = self.next_revision(extraction_id)
            change = ADD if _canon(previous) is None else CLEAR if _canon(corrected) is None else EDIT
            row = _row(key, change, None, previous, corrected)
            row.update({
                "extraction_id": extraction_id, "document_id": document["id"],
                "case_id": document.get("case_id"), "revision": revision, "corrected_by": reviewer_id,
            })
            self.repo.bulk_insert(TABLE, [row])
            return True
        except Exception as e:
            logger.error("corrections.page_record_failed | document_id=%s error=%s", document.get("id"), e)
            return False
