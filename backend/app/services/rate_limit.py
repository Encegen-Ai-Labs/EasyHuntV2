"""Recognizes Gemini rate-limit (HTTP 429 / RESOURCE_EXHAUSTED) failures.

Used only to *label* a failure so the document queue (app/tasks/document_tasks.py)
can retry it later with backoff. It never alters what an extraction call
returns on success, and never changes how a failure is handled in-process.
"""

from typing import Optional


class RateLimited(Exception):
    """Raised by the queue task to trigger a backoff retry after the pipeline
    reported that Gemini rate-limited it."""


def is_rate_limit_error(exc: Optional[BaseException]) -> bool:
    if exc is None:
        return False
    if getattr(exc, "code", None) == 429 or getattr(exc, "status_code", None) == 429:
        return True
    status = str(getattr(exc, "status", "") or "").upper()
    if status == "RESOURCE_EXHAUSTED":
        return True
    text = str(exc)
    return "429" in text and "RESOURCE_EXHAUSTED" in text.upper()
