"""Request tracing, safe error responses, security headers and error tracking.

Every request gets an id (taken from an X-Request-ID header when a proxy
supplies one) that appears on every log line it causes and in the response, so
"it failed at 3:40" can be turned into the exact log lines. Unexpected errors
are answered with a generic message plus that id; the real error goes to the
log (scrubbed) and to Sentry, never to the user.
"""
import re
import time
import uuid
from typing import Any, Dict, Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

from app.core import context
from app.core.config import settings
from app.core.logging import logger
from app.core.rate_limiting import limit_everything

_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
_UNLIMITED_PATHS = ("/health", "/openapi.json")

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


def _request_id(request: Request) -> str:
    supplied = request.headers.get("x-request-id", "")
    return supplied if _SAFE_REQUEST_ID.match(supplied) else uuid.uuid4().hex


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Request id, blanket rate limit, access log, security headers, and a
    safe answer to anything unexpected."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = _request_id(request)
        context.bind(request_id=request_id, user_id=None, case_id=None, document_id=None)
        started = time.monotonic()
        path = request.url.path

        if request.method != "OPTIONS" and not path.startswith(_UNLIMITED_PATHS) and not limit_everything(request):
            logger.warning("http.rate_limited | method=%s path=%s", request.method, path)
            response: Response = JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please wait a minute and try again."},
                headers={"Retry-After": "60"},
            )
        else:
            try:
                response = await call_next(request)
            except Exception as exc:  # anything the route handlers did not turn into a response
                logger.exception("http.unhandled_error | method=%s path=%s", request.method, path)
                capture_exception(exc)
                response = JSONResponse(
                    status_code=500,
                    content={"detail": f"Something went wrong on our side. Quote this reference if you report it: {request_id}"},
                )

        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        if settings.is_production or request.headers.get("x-forwarded-proto") == "https":
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        response.headers.setdefault("Cache-Control", "no-store")
        response.headers["X-Request-ID"] = request_id

        if not path.startswith(_UNLIMITED_PATHS):
            logger.info(
                "http.request | method=%s path=%s status=%s duration_ms=%s user_id=%s",
                request.method, path, response.status_code, int((time.monotonic() - started) * 1000),
                getattr(request.state, "user_id", None) or "-",
            )
        return response


# ---- error tracking ------------------------------------------------------------

_sentry_ready = False


def scrub_event(event: Dict[str, Any], hint: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """Removes everything that could carry client data or credentials from a
    Sentry event before it leaves the server: request bodies, headers, cookies,
    query strings and user details. What remains is the stack trace and the
    request path."""
    request = event.get("request") or {}
    for field in ("data", "headers", "cookies", "query_string", "env"):
        request.pop(field, None)
    event["request"] = request
    event.pop("user", None)
    event.pop("server_name", None)
    return event


def init_sentry() -> bool:
    global _sentry_ready
    if not settings.SENTRY_DSN:
        return False
    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.APP_ENV,
        send_default_pii=False,
        traces_sample_rate=0.0,
        before_send=scrub_event,
    )
    _sentry_ready = True
    logger.info("sentry.enabled | environment=%s", settings.APP_ENV)
    return True


def capture_exception(exc: BaseException) -> None:
    if not _sentry_ready:
        return
    import sentry_sdk

    sentry_sdk.capture_exception(exc)
