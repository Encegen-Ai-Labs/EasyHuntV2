"""Content-hash cache for document extraction (docs/EXTRACTION_QUALITY.md 2.1, 8.2).

Key = sha256(file bytes) + model + pipeline_version. The same file extracted
with the same model and the same pipeline returns the stored result instead of
calling Gemini again.

What is stored is everything the pipeline needs to skip the expensive steps
and carry on exactly as if it had just run them: the per-page routing results
(page text, source, handwriting flag...) and the structured-field result.

pipeline_version is computed, never hand-bumped: it hashes the prompts, the
source of every function that builds a model call, the source of the router,
OCR provider and image enhancement, and the settings that change what they
produce. Editing any of them makes old entries unreachable.

Never cached: a failed extraction (including a rate-limited one), a result
where any page failed to transcribe. Any cache error is a miss, never a
failed document.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import os
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol

from app.core.config import settings
from app.core.logging import logger

TABLE = "extraction_cache"

# validation_errors entry written on a cache hit, so the review screen can
# show where the result came from. The frontend matches on this prefix.
CACHED_RESULT_PREFIX = "cached_result:"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@lru_cache(maxsize=1)
def pipeline_version() -> str:
    """Short hash of everything that determines what the pipeline outputs
    for a given file. Computed once per process."""
    # Imported here: these modules import config/clients at import time.
    from app.ocr import tesseract_provider
    from app.services import document_router, image_enhancement, llm_extractor, page_extraction_service as pes

    parts: List[str] = [
        llm_extractor.GEMINI_MODEL,
        llm_extractor.STRUCTURED_EXTRACTION_FROM_TEXT_PROMPT,
        pes.PAGE_TRANSCRIPTION_PROMPT,
        pes.PAGE_TRANSCRIPTION_AND_EXTRACTION_PROMPT,
        pes.FIELDS_DELIMITER,
        repr((pes.RASTER_DPI, pes.MAX_IMAGE_DIMENSION_PX)),
        repr((settings.ROUTER_HANDWRITING_THRESHOLD, settings.OCR_FALLBACK_CONFIDENCE,
              settings.TESSERACT_LANGUAGES)),
        # Function bodies carry the generation config (temperature, seed,
        # response schema, retries) and the fixups applied to model output.
        inspect.getsource(llm_extractor.extract_structured_fields_from_text),
        inspect.getsource(pes.extract_page_text),
        inspect.getsource(pes.extract_page_text_and_fields),
        inspect.getsource(pes.strip_annotation_tags),
        inspect.getsource(pes.rasterize_pages),
        inspect.getsource(document_router),
        inspect.getsource(image_enhancement),
        inspect.getsource(tesseract_provider),
    ]
    # Normalise line endings so a CRLF checkout and an LF checkout agree.
    blob = "\x1f".join(p.replace("\r\n", "\n") for p in parts)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


def make_key(content_sha256: str, model: str, version: str) -> str:
    return hashlib.sha256(f"{content_sha256}|{model}|{version}".encode("utf-8")).hexdigest()


def pages_are_cacheable(routed_pages: List[Dict[str, Any]]) -> bool:
    """A document with any failed page is never cached: a later attempt
    should get another chance at that page."""
    for p in routed_pages:
        if p is None or p.get("source") == "error":
            return False
        if str(p.get("original_text", "")).startswith("[page extraction failed"):
            return False
        if any(str(i).startswith("vlm_error") for i in p.get("issues", [])):
            return False
    return True


class CacheStore(Protocol):
    def get(self, key: str) -> Optional[Dict[str, Any]]: ...
    def put(self, row: Dict[str, Any]) -> None: ...


class SupabaseCacheStore:
    """extraction_cache table (migrations/0007_extraction_cache.sql)."""

    def __init__(self, client: Any):
        self.client = client

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        res = self.client.table(TABLE).select("*").eq("key", key).limit(1).execute()
        return res.data[0] if res.data else None

    def put(self, row: Dict[str, Any]) -> None:
        self.client.table(TABLE).upsert(row, on_conflict="key").execute()


class FileCacheStore:
    """One JSON file per key. For the eval/variance scripts and tests, which
    have no Supabase."""

    def __init__(self, directory: Path):
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.dir / f"{key}.json"

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        try:
            return json.loads(self._path(key).read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None

    def put(self, row: Dict[str, Any]) -> None:
        tmp = self._path(row["key"]).with_suffix(".tmp")
        tmp.write_text(json.dumps(row, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self._path(row["key"]))


class ExtractionCache:
    def __init__(self, store: CacheStore, version: Optional[str] = None, model: Optional[str] = None):
        from app.services.llm_extractor import GEMINI_MODEL
        self.store = store
        self.model = model or GEMINI_MODEL
        self.version = version or pipeline_version()

    def key_for(self, content_sha256: str) -> str:
        return make_key(content_sha256, self.model, self.version)

    def get(self, content_sha256: str) -> Optional[Dict[str, Any]]:
        """Returns {routed_pages, extracted, model_used, created_at} or None."""
        key = self.key_for(content_sha256)
        try:
            row = self.store.get(key)
        except Exception as e:
            logger.error("extraction_cache.read_failed | key=%s error=%s", key[:12], e)
            return None
        if not row:
            return None
        result = row.get("result") or {}
        if not isinstance(result.get("routed_pages"), list) or not isinstance(result.get("extracted"), dict):
            logger.error("extraction_cache.entry_malformed | key=%s", key[:12])
            return None
        return {
            "routed_pages": result["routed_pages"],
            "extracted": result["extracted"],
            "model_used": result.get("model_used") or self.model,
            "created_at": row.get("created_at"),
        }

    def put(self, content_sha256: str, routed_pages: List[Dict[str, Any]], extraction: Dict[str, Any]) -> bool:
        """Stores a successful extraction. Returns whether it was stored."""
        if not extraction.get("success") or not isinstance(extraction.get("extracted"), dict):
            return False
        if not pages_are_cacheable(routed_pages):
            return False
        key = self.key_for(content_sha256)
        row = {
            "key": key,
            "content_sha256": content_sha256,
            "model": self.model,
            "pipeline_version": self.version,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "result": {
                "routed_pages": routed_pages,
                "extracted": extraction["extracted"],
                "model_used": extraction.get("model_used") or self.model,
            },
        }
        try:
            self.store.put(row)
            return True
        except Exception as e:
            logger.error("extraction_cache.write_failed | key=%s error=%s", key[:12], e)
            return False


def cache_note(entry: Dict[str, Any], version: str) -> str:
    when = entry.get("created_at") or "an earlier upload"
    return (
        f"{CACHED_RESULT_PREFIX} the same file was extracted before; the saved result from {when} "
        f"(pipeline {version}) was reused. Upload again with 'Ignore saved results' for a fresh extraction."
    )


def build_cache(client: Any) -> Optional[ExtractionCache]:
    """The app's cache, or None when EXTRACTION_CACHE_ENABLED is off."""
    if not settings.EXTRACTION_CACHE_ENABLED:
        return None
    return ExtractionCache(SupabaseCacheStore(client))
