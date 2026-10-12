import json
import logging
import os
import re
import sys
from datetime import datetime, timezone

from app.core import context
from app.core.redaction import redact

# "pipeline.rasterized | document_id=abc pages=3": the codebase's existing log
# convention. The JSON formatter turns the part after " | " into real fields so
# a log search can filter on document_id, status and so on.
_KEY_VALUE = re.compile(r"(\w+)=(\S+)")
_RESERVED = {"ts", "level", "logger", "event", "message", "exception"}


def _use_json() -> bool:
    chosen = os.environ.get("LOG_FORMAT", "").lower()
    if chosen in ("json", "text"):
        return chosen == "json"
    return os.environ.get("APP_ENV", "development").lower() in ("production", "staging")


class RedactingTextFormatter(logging.Formatter):
    """The familiar one-line format, with secrets removed from the whole line
    (message and traceback alike)."""

    def format(self, record: logging.LogRecord) -> str:
        line = super().format(record)
        ctx = context.current()
        tag = f" [req={ctx['request_id']}]" if ctx.get("request_id") else ""
        return redact(line.replace(": ", f"{tag}: ", 1) if tag else line)


class RedactingJsonFormatter(logging.Formatter):
    """One JSON object per line: easy to ship and to search. Never contains
    document text (callers log ids, not content) or secrets."""

    def format(self, record: logging.LogRecord) -> str:
        message = redact(record.getMessage())
        event, _, rest = message.partition(" | ")
        entry = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "event": event if rest else None,
            "message": message,
        }
        if rest:
            for key, value in _KEY_VALUE.findall(rest):
                entry.setdefault(key if key not in _RESERVED else f"field_{key}", value)
        for key, value in context.current().items():
            entry.setdefault(key, value)
        if record.exc_info:
            entry["exception"] = redact(self.formatException(record.exc_info))
        return json.dumps({k: v for k, v in entry.items() if v is not None}, ensure_ascii=False)


def setup_logging():
    handler = logging.StreamHandler(sys.stdout)
    if _use_json():
        handler.setFormatter(RedactingJsonFormatter())
    else:
        handler.setFormatter(RedactingTextFormatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers = [handler]
    if os.environ.get("ERROR_STORE_ENABLED", "true").lower() == "true":
        from app.core.error_store import ErrorStoreHandler

        root.addHandler(ErrorStoreHandler())
    root.setLevel(logging.INFO)
    # httpx logs every request URL at INFO; our URLs carry no secrets any more,
    # but there is no reason to log every Supabase call either.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logger = logging.getLogger("property_verification")
    logger.setLevel(logging.INFO)
    return logger


logger = setup_logging()
