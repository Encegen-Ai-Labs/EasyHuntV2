"""Per-request / per-document context that every log line and usage record carries.

Context variables follow the work: FastAPI copies them into its worker threads,
and the pipeline and Celery task bind the document and case they are working on.
"""
from contextvars import ContextVar
from typing import Optional

request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
user_id_var: ContextVar[Optional[str]] = ContextVar("user_id", default=None)
case_id_var: ContextVar[Optional[str]] = ContextVar("case_id", default=None)
document_id_var: ContextVar[Optional[str]] = ContextVar("document_id", default=None)

_VARS = {
    "request_id": request_id_var,
    "user_id": user_id_var,
    "case_id": case_id_var,
    "document_id": document_id_var,
}


def bind(**values: Optional[str]) -> None:
    """Sets any of request_id, user_id, case_id, document_id (None clears one)."""
    for name, value in values.items():
        _VARS[name].set(None if value is None else str(value))


def current() -> dict:
    """The non-empty context values, for logging and for usage records."""
    return {name: var.get() for name, var in _VARS.items() if var.get()}
