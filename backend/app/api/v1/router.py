from fastapi import APIRouter

from app.api.v1.admin import router as admin_router
from app.api.v1.auth import router as auth_router
from app.api.v1.cases import router as cases_router
from app.api.v1.documents import router as documents_router
from app.api.v1.flags import router as flags_router
from app.api.v1.reports import router as reports_router
from app.api.v1.review import router as review_router

router = APIRouter()

router.include_router(auth_router)
router.include_router(admin_router)
router.include_router(cases_router)
router.include_router(documents_router)
router.include_router(flags_router)
router.include_router(reports_router)
router.include_router(review_router)


@router.get("/health")
async def api_health_check():
    return {"status": "ok", "module": "api-v1"}
