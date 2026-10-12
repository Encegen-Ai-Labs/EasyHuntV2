"""Request rate limits, as FastAPI dependencies.

    @router.post("/login", dependencies=[Depends(limit_ip("login", "RATE_LIMIT_LOGIN"))])

Two keys: the client address (for endpoints with no login yet, so a stranger
cannot guess passwords all day) and the signed-in user (for anything that spends
money or CPU, so one account cannot run up the bill). The rate itself is read
from settings on every request, so changing the setting or a test's patch takes
effect immediately.

If the limit store (Redis) is unreachable the request is allowed and the problem
is logged: a broken limiter must not lock the lawyers out of their cases.
"""
from typing import Any, Callable, Dict, Optional

from fastapi import Depends, HTTPException, Request, status
from limits import parse
from limits.storage import MemoryStorage, storage_from_string
from limits.strategies import FixedWindowRateLimiter

from app.core.config import settings
from app.core.logging import logger
from app.core.redaction import safe_error
from app.dependencies.auth import get_current_user

RETRY_AFTER_SECONDS = "60"
_limiter: Optional[FixedWindowRateLimiter] = None
_limiter_url: Optional[str] = None


def _get_limiter() -> FixedWindowRateLimiter:
    global _limiter, _limiter_url
    if _limiter is None or _limiter_url != settings.RATE_LIMIT_STORAGE_URL:
        try:
            storage = storage_from_string(settings.RATE_LIMIT_STORAGE_URL)
        except Exception as exc:
            logger.error("rate_limit.storage_unavailable | reason=%s using=memory", safe_error(exc, 160))
            storage = MemoryStorage()
        _limiter, _limiter_url = FixedWindowRateLimiter(storage), settings.RATE_LIMIT_STORAGE_URL
    return _limiter


def client_ip(request: Request) -> str:
    """The caller's address. Behind a trusted reverse proxy the real address is
    the first X-Forwarded-For entry; without one that header is attacker-controlled."""
    if settings.TRUST_PROXY:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def hit(scope: str, rate: str, key: str) -> bool:
    """Counts one request. True if it is within the limit (or limiting is off or broken)."""
    if not settings.RATE_LIMIT_ENABLED:
        return True
    try:
        return _get_limiter().hit(parse(rate), scope, key)
    except Exception as exc:
        logger.error("rate_limit.check_failed | scope=%s reason=%s", scope, safe_error(exc, 160))
        return True


def _too_many() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Too many requests. Please wait a minute and try again.",
        headers={"Retry-After": RETRY_AFTER_SECONDS},
    )


def limit_ip(scope: str, rate_setting: str) -> Callable[..., None]:
    def dependency(request: Request) -> None:
        if not hit(scope, getattr(settings, rate_setting), client_ip(request)):
            logger.warning("rate_limit.exceeded | scope=%s by=ip", scope)
            raise _too_many()

    return dependency


def limit_user(scope: str, rate_setting: str) -> Callable[..., None]:
    def dependency(current_user: Dict[str, Any] = Depends(get_current_user)) -> None:
        if not hit(scope, getattr(settings, rate_setting), str(current_user["id"])):
            logger.warning("rate_limit.exceeded | scope=%s by=user user_id=%s", scope, current_user["id"])
            raise _too_many()

    return dependency


def limit_everything(request: Request) -> bool:
    """The blanket per-address limit applied by the middleware to every API call."""
    return hit("all", settings.RATE_LIMIT_DEFAULT, client_ip(request))
