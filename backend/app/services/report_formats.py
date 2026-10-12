"""The report formats a lawyer can choose from.

One generic "Title Search Report", plus one entry per bank template in
templates/scrutiny_reports/ (each .docx has a .fields.json manifest that names
the bank and lists every field and repeating table the template fills).
"Upload a bank's own format" is not available yet and is not listed here.
"""
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

from app.core.exceptions import ResourceNotFoundError

TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent / "templates" / "scrutiny_reports"
TITLE_SEARCH_ID = "title-search"
MANIFEST_SUFFIX = ".fields.json"


@lru_cache(maxsize=1)
def _manifests() -> Dict[str, Dict[str, Any]]:
    manifests: Dict[str, Dict[str, Any]] = {}
    for path in sorted(TEMPLATE_DIR.glob(f"*{MANIFEST_SUFFIX}")):
        with open(path, encoding="utf-8") as handle:
            manifests[path.name[: -len(MANIFEST_SUFFIX)]] = json.load(handle)
    return manifests


def list_formats() -> List[Dict[str, str]]:
    title_search = {
        "id": TITLE_SEARCH_ID,
        "kind": "title_search",
        "label": "Title Search Report / Legal Search Report",
    }
    banks = [
        {"id": format_id, "kind": "bank", "label": manifest.get("bank") or format_id}
        for format_id, manifest in _manifests().items()
    ]
    return [title_search] + sorted(banks, key=lambda f: f["label"].lower())


def get_manifest(format_id: str) -> Dict[str, Any]:
    """The manifest for a bank format id. Only ids that exist as a manifest are
    accepted, so a caller-supplied id can never name another file."""
    manifest = _manifests().get(format_id)
    if manifest is None:
        raise ResourceNotFoundError("Unknown report format")
    return manifest


def template_path(format_id: str) -> Path:
    return TEMPLATE_DIR / get_manifest(format_id)["template"]


def is_title_search(format_id: str) -> bool:
    return format_id == TITLE_SEARCH_ID
