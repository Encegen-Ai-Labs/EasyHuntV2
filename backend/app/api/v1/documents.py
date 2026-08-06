from fastapi import APIRouter, Depends, UploadFile, File, Form, status, BackgroundTasks
from app.schemas.documents import DocumentResponse
from app.services.doc_service import DocumentService
from app.services.pipeline_service import PipelineService
from app.repositories.doc_repo import DocumentRepository
from app.repositories.case_repo import CaseRepository
from app.repositories.flag_repo import FlagRepository
from app.dependencies.db import get_supabase_client
from app.dependencies.auth import RoleRequirement
from supabase import Client
from typing import Dict, Any

router = APIRouter(prefix="/documents", tags=["Document Infrastructure"])

def get_doc_service(db: Client = Depends(get_supabase_client)) -> DocumentService:
    return DocumentService(DocumentRepository(db), CaseRepository(db))

def get_pipeline_service(db: Client = Depends(get_supabase_client)) -> PipelineService:
    return PipelineService(DocumentRepository(db), CaseRepository(db), FlagRepository(db))

@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    case_id: str = Form(...),
    file: UploadFile = File(...),
    current_user: Dict[str, Any] = Depends(RoleRequirement(["Vendor", "Admin"])),
    service: DocumentService = Depends(get_doc_service)
):
    file_bytes = await file.read()
    return service.validate_and_upload(
        case_id=case_id,
        file_name=file.filename,
        file_bytes=file_bytes,
        mime_type=file.content_type,
        current_user=current_user
    )

@router.post("/{id}/process")
def process_document(
    id: str,
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(RoleRequirement(["Reviewer", "Admin"])),
    pipeline_service: PipelineService = Depends(get_pipeline_service)
):
    # Enqueue execution asynchronously inside the FastAPI event loop
    background_tasks.add_task(pipeline_service.execute_analysis_pipeline, id)
    return {"message": f"Processing pipeline initiated for document {id}"}