"""Keeps every error-level log line where an admin can read it.

Container logs vanish when the container is replaced and nobody reads them
unprompted. This handler copies each ERROR (and exception) log record into the
app_errors table, with secrets removed, so the admin screen can list what went
wrong, when, for which user, case and document.

It never gets in the way: records go onto a small in-memory queue and a
background thread inserts them; if the queue is full or the database cannot be
reached the record is dropped (it is still in the container log), and the
handler never logs about itself.
"""
import logging
import queue
import threading
import time
from typing import Any, Dict, Optional

from app.core import context
from app.core.redaction import redact

TABLE = "app_errors"
MAX_MESSAGE = 600
QUEUE_SIZE = 200
BACKOFF_SECONDS = 120


class ErrorStoreHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.ERROR)
        self._queue: "queue.Queue[Dict[str, Any]]" = queue.Queue(maxsize=QUEUE_SIZE)
        self._paused_until = 0.0
        self._thread: Optional[threading.Thread] = None

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = redact(record.getMessage())
            event, _, _ = message.partition(" | ")
            ctx = context.current()
            row = {
                "event": event[:120] if " | " in message else None,
                "message": message[:MAX_MESSAGE],
                "logger": record.name,
                "exception": type(record.exc_info[1]).__name__ if record.exc_info and record.exc_info[1] else None,
                "request_id": ctx.get("request_id"),
                "user_id": ctx.get("user_id"),
                "case_id": ctx.get("case_id"),
                "document_id": ctx.get("document_id"),
            }
            self._queue.put_nowait(row)
            self._ensure_worker()
        except Exception:
            pass  # never let error recording raise or recurse

    def _ensure_worker(self) -> None:
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._run, name="error-store", daemon=True)
            self._thread.start()

    def _run(self) -> None:
        while True:
            row = self._queue.get()
            if time.monotonic() < self._paused_until:
                continue
            try:
                from app.dependencies.db import get_supabase_service_client

                get_supabase_service_client().table(TABLE).insert(row).execute()
            except Exception:
                self._paused_until = time.monotonic() + BACKOFF_SECONDS
