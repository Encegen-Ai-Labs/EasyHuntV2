from fastapi import APIRouter

from app.api.v1.auth import router as auth_router

router = APIRouter()

router.include_router(auth_router)


@router.get("/health")
async def api_health_check():
    return {"status": "ok", "module": "api-v1"}
