from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from app.api.v1 import router as v1_router
from app.core.config import settings
from app.core.exceptions import PropertySystemException
from app.core.logging import logger
from app.core.redaction import safe_error
from app.dependencies.db import get_supabase_service_client
from app.core.observability import RequestContextMiddleware, init_sentry
from app.core.startup_checks import run as run_startup_checks

run_startup_checks(settings)
init_sentry()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    openapi_url="/openapi.json",
)

# Added before CORS so CORS stays outermost: even a safe 500 or 429 then carries
# the CORS headers and the browser shows the real message, not "failed to fetch".
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "Retry-After"],
)


@app.exception_handler(PropertySystemException)
async def property_system_exception_handler(request: Request, exc: PropertySystemException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": settings.PROJECT_NAME}


@app.get("/health/ready")
def readiness_check():
    """Can this instance do real work? Checks the database and, when the queue is
    on, Redis. A deploy waits for this to answer 200 before it counts as live,
    and an uptime monitor should watch it rather than /health."""
    checks = {}
    try:
        get_supabase_service_client().table("users").select("id").limit(1).execute()
        checks["database"] = "ok"
    except Exception as exc:
        logger.error("health.database_down | reason=%s", safe_error(exc, 160))
        checks["database"] = "down"
    if settings.CELERY_ENABLED:
        try:
            import redis

            redis.Redis.from_url(settings.CELERY_BROKER_URL, socket_connect_timeout=2).ping()
            checks["queue"] = "ok"
        except Exception as exc:
            logger.error("health.queue_down | reason=%s", safe_error(exc, 160))
            checks["queue"] = "down"
    healthy = all(value == "ok" for value in checks.values())
    return JSONResponse(status_code=200 if healthy else 503, content={"status": "ok" if healthy else "degraded", "checks": checks})


@app.get("/")
async def root():
    return {"message": f"{settings.PROJECT_NAME} is running"}


app.include_router(v1_router, prefix=settings.API_V1_STR)

logger.info("FastAPI application initialized")