from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from app.api.v1 import router as v1_router
from app.core.config import settings
from app.core.exceptions import PropertySystemException
from app.core.logging import logger

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(PropertySystemException)
async def property_system_exception_handler(request: Request, exc: PropertySystemException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": settings.PROJECT_NAME}


@app.get("/")
async def root():
    return {"message": f"{settings.PROJECT_NAME} is running"}


app.include_router(v1_router, prefix=settings.API_V1_STR)

logger.info("FastAPI application initialized")