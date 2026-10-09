"""Loads and validates evaluation cases from <data_dir>/cases/<case_id>/.

Validation is strict on purpose: a field that is neither labelled nor listed
under `unlabelled` is an error, so a typo can never silently drop a field
from the score.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .scorers import FIELD_KINDS, LIST_FIELDS, SCALAR_FIELDS

SCHEMA_VERSION = 1
SPLITS = ("example", "holdout")
HANDWRITING = ("none", "partial", "full")
DOCUMENT_TYPES = (
    "sale_deed", "mutation_record", "tax_receipt", "encumbrance_certificate",
    "partition_deed", "gift_deed", "other",
)
SOURCE_EXTENSIONS = (".pdf", ".png", ".jpg", ".jpeg", ".webp")


class EvalDataError(Exception):
    pass


@dataclass
class Case:
    id: str
    path: Path
    meta: Dict[str, Any]
    expected: Dict[str, Any]
    source_path: Optional[Path]
    source_sha256: Optional[str]
    transcript_path: Optional[Path]

    @property
    def split(self) -> str:
        return self.meta["split"]

    @property
    def document_type(self) -> str:
        return self.meta["document_type"]


def default_data_dir() -> Path:
    env = os.environ.get("EVAL_DATA_DIR")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2] / "eval_data"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_meta(meta: Dict[str, Any], case_id: str) -> None:
    for key in ("id", "document_type", "split", "handwriting"):
        if key not in meta:
            raise EvalDataError(f"{case_id}: meta.json missing '{key}'")
    if meta["id"] != case_id:
        raise EvalDataError(f"{case_id}: meta.json id '{meta['id']}' does not match the folder name")
    if meta["document_type"] not in DOCUMENT_TYPES:
        raise EvalDataError(f"{case_id}: document_type '{meta['document_type']}' not one of {DOCUMENT_TYPES}")
    if meta["split"] not in SPLITS:
        raise EvalDataError(f"{case_id}: split '{meta['split']}' must be one of {SPLITS}")
    if meta["handwriting"] not in HANDWRITING:
        raise EvalDataError(f"{case_id}: handwriting '{meta['handwriting']}' must be one of {HANDWRITING}")


def validate_expected(expected: Dict[str, Any], case_id: str) -> None:
    if expected.get("schema_version") != SCHEMA_VERSION:
        raise EvalDataError(f"{case_id}: expected.json schema_version must be {SCHEMA_VERSION}")
    fields = expected.get("fields")
    if not isinstance(fields, dict):
        raise EvalDataError(f"{case_id}: expected.json needs a 'fields' object")
    unlabelled = expected.get("unlabelled", [])
    if not isinstance(unlabelled, list):
        raise EvalDataError(f"{case_id}: 'unlabelled' must be a list")
    known = set(SCALAR_FIELDS) | set(LIST_FIELDS)
    for name in list(fields) + list(unlabelled):
        if name not in known:
            raise EvalDataError(f"{case_id}: unknown field '{name}'")
    for name in SCALAR_FIELDS:
        if name not in fields and name not in unlabelled:
            raise EvalDataError(
                f"{case_id}: field '{name}' is neither labelled nor listed under 'unlabelled' "
                "(use null for 'the correct answer is null')"
            )
    for name in LIST_FIELDS:
        if name in unlabelled:
            continue
        if name not in expected:
            # chain / red_flags: absent means not labelled.
            unlabelled.append(name)
            expected["unlabelled"] = unlabelled
        elif not isinstance(expected[name], list):
            raise EvalDataError(f"{case_id}: '{name}' must be a list")
    for name, alts in expected.get("alternates", {}).items():
        if name not in FIELD_KINDS or not isinstance(alts, list):
            raise EvalDataError(f"{case_id}: bad 'alternates' entry for '{name}'")
    for name in expected.get("transliterations", {}):
        if FIELD_KINDS.get(name) != "name":
            raise EvalDataError(f"{case_id}: 'transliterations' only applies to name fields, not '{name}'")


def _read_json(path: Path, case_id: str) -> Dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise EvalDataError(f"{case_id}: missing {path.name}")
    except json.JSONDecodeError as e:
        raise EvalDataError(f"{case_id}: {path.name} is not valid JSON ({e})")


def load_case(case_dir: Path) -> Case:
    case_id = case_dir.name
    meta = _read_json(case_dir / "meta.json", case_id)
    expected = _read_json(case_dir / "expected.json", case_id)
    validate_meta(meta, case_id)
    validate_expected(expected, case_id)
    source = next(
        (p for p in sorted(case_dir.iterdir()) if p.stem == "source" and p.suffix.lower() in SOURCE_EXTENSIONS),
        None,
    )
    transcript = case_dir / "transcript.txt"
    return Case(
        id=case_id, path=case_dir, meta=meta, expected=expected,
        source_path=source, source_sha256=sha256_file(source) if source else None,
        transcript_path=transcript if transcript.exists() else None,
    )


def load_cases(data_dir: Path, split: str = "holdout") -> List[Case]:
    """split: 'holdout' (default, the headline set), 'example', or 'all'."""
    cases_dir = Path(data_dir) / "cases"
    if not cases_dir.is_dir():
        raise EvalDataError(f"no cases/ folder under {data_dir}")
    cases = [load_case(d) for d in sorted(cases_dir.iterdir()) if d.is_dir()]
    check_no_leakage(cases)
    if split == "all":
        return cases
    if split not in SPLITS:
        raise EvalDataError(f"--split must be one of {SPLITS + ('all',)}")
    return [c for c in cases if c.split == split]


def check_no_leakage(cases: List[Case]) -> None:
    """The same source file must never appear in both splits (a duplicate
    under another folder name would inflate the holdout score)."""
    seen: Dict[str, Case] = {}
    for c in cases:
        if not c.source_sha256:
            continue
        other = seen.get(c.source_sha256)
        if other and other.split != c.split:
            raise EvalDataError(
                f"{c.id} ({c.split}) and {other.id} ({other.split}) have identical source files: "
                "an example document would leak into the holdout score"
            )
        seen.setdefault(c.source_sha256, c)
