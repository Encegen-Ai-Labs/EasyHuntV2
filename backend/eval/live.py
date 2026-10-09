"""Optional live mode: run the current extraction on a case's source file.

NEEDS GEMINI_API_KEY and makes real Gemini calls. The test suite never uses
this module with real dependencies: tests pass fake `LiveDeps`.

This re-composes the pipeline's steps from the existing building blocks
(rasterize -> enhance -> route -> field extraction). It does NOT call
PipelineService.execute_analysis_pipeline, which needs Supabase. The
orchestration below mirrors pipeline_service.py lines ~259-358 and is a
known duplicate: once the pr27 branch is merged, the plan (section 1.5) is to
extract a DB-free `extract_document_bytes()` from the pipeline and have this
call it, so the two cannot drift. Until then, a change to the pipeline's
orchestration must be mirrored here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Tuple

MIME_BY_EXT = {
    ".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg", ".webp": "image/webp",
}


@dataclass
class LiveDeps:
    rasterize: Callable[[bytes, str], List[bytes]]
    enhance: Callable[[bytes], Tuple[bytes, Dict[str, Any]]]
    route: Callable[..., Dict[str, Any]]
    extract_fields: Callable[[str], Dict[str, Any]]
    strip_tags: Callable[[str], str]


def default_deps() -> LiveDeps:
    # Imported here, not at module top: importing the app's services loads
    # its settings and the Gemini client, which the offline harness and the
    # tests must not do.
    from app.services.document_router import route_and_extract_page
    from app.services.image_enhancement import enhance_page_image_with_report
    from app.services.llm_extractor import extract_structured_fields_from_text
    from app.services.page_extraction_service import rasterize_pages, strip_annotation_tags

    return LiveDeps(
        rasterize=rasterize_pages,
        enhance=enhance_page_image_with_report,
        route=route_and_extract_page,
        extract_fields=extract_structured_fields_from_text,
        strip_tags=strip_annotation_tags,
    )


def _merge(routed: List[Dict[str, Any]]) -> str:
    return "\n\n".join(f"--- Page {p['page_number']} ---\n{p['original_text']}" for p in routed)


def extract_case(case, stage: str, deps: LiveDeps) -> Dict[str, Any]:
    """Returns an extraction dict shaped like validated_json_output, plus
    `_meta` ({source, stage}); on failure returns {"_error": ...}."""
    try:
        if stage == "fields-only":
            if not case.transcript_path:
                return {"_error": "fields-only stage needs transcript.txt in the case folder"}
            text = case.transcript_path.read_text(encoding="utf-8")
            result = deps.extract_fields(deps.strip_tags(text))
            if not result["success"]:
                return {"_error": result["error"]}
            extracted = dict(result["extracted"])
            extracted["full_text"] = text
            extracted["_meta"] = {"stage": stage, "source": None}
            return extracted

        if not case.source_path:
            return {"_error": "no source file in the case folder"}
        mime = MIME_BY_EXT.get(case.source_path.suffix.lower(), "application/pdf")
        pages = deps.rasterize(case.source_path.read_bytes(), mime)
        combine = len(pages) == 1
        routed = []
        for i, image in enumerate(pages):
            enhanced = deps.enhance(image)[0]
            routed.append(deps.route(enhanced, page_number=i + 1, also_extract_fields=combine))
        merged = _merge(routed)

        combined = routed[0].get("structured_fields") if combine else None
        if combined is not None:
            extracted = dict(combined)
        else:
            result = deps.extract_fields(deps.strip_tags(merged))
            if not result["success"]:
                return {"_error": result["error"]}
            extracted = dict(result["extracted"])
        extracted["full_text"] = merged
        extracted["has_handwritten_content"] = any(p["has_handwriting"] for p in routed)
        extracted["_meta"] = {
            "stage": stage,
            "source": "vlm" if any(p["source"] == "vlm" for p in routed) else "ocr",
            "page_sources": [p["source"] for p in routed],
        }
        return extracted
    except Exception as e:  # one bad document must not abort the run
        return {"_error": f"{type(e).__name__}: {e}"}
