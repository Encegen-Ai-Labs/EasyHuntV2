from fastapi import APIRouter, Depends, status
from typing import List, Dict, Any
from app.schemas.cases import CaseCreate, CaseResponse, CaseUpdate
from app.services.case_service import CaseService
from app.services.pipeline_service import PipelineService
from app.repositories.case_repo import CaseRepository
from app.repositories.doc_repo import DocumentRepository
from app.repositories.flag_repo import FlagRepository
from app.dependencies.db import get_supabase_client
from app.dependencies.auth import get_current_user, RoleRequirement
from supabase import Client

router = APIRouter(prefix="/cases", tags=["Case Management"])

def get_case_service(db: Client = Depends(get_supabase_client)) -> CaseService:
    return CaseService(CaseRepository(db))

def get_pipeline_service(db: Client = Depends(get_supabase_client)) -> PipelineService:
    return PipelineService(DocumentRepository(db), CaseRepository(db), FlagRepository(db))

@router.post("", response_model=CaseResponse, status_code=status.HTTP_201_CREATED)
def create_case(
    payload: CaseCreate,
    current_user: Dict[str, Any] = Depends(RoleRequirement(["Vendor", "Admin"])),
    service: CaseService = Depends(get_case_service)
):
    return service.create(
        vendor_id=str(current_user["id"]),
        property_name=payload.property_name,
        survey_number=payload.survey_number,
        location=payload.location
    )

@router.get("", response_model=List[CaseResponse])
def list_cases(
    current_user: Dict[str, Any] = Depends(get_current_user),
    service: CaseService = Depends(get_case_service)
):
    return service.list_cases(current_user)

@router.get("/{id}", response_model=CaseResponse)
def get_case_by_id(
    id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    service: CaseService = Depends(get_case_service)
):
    return service.retrieve(id, current_user)

def get_pipeline_service(db: Client = Depends(get_supabase_client)) -> PipelineService:
    return PipelineService(DocumentRepository(db), CaseRepository(db), FlagRepository(db))

@router.post("/{case_id}/finalize")
def finalize_case(
    case_id: str,
    current_user: Dict[str, Any] = Depends(RoleRequirement(["Reviewer", "Admin"])),
    pipeline_service: PipelineService = Depends(get_pipeline_service)
):
    return pipeline_service.finalize_case(case_id)