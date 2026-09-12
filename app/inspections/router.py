import os
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, BackgroundTasks, status
from fastapi.responses import FileResponse
from app.auth.router import get_current_user
from app.config import settings
from .service import InspectionService
from .models import (
    InspectionStatus,
    EvidenceResponse,
    InspectionCreateResponse,
    HistoryResponse
)

router = APIRouter(prefix="/api/inspections", tags=["inspections"])

inspection_service = InspectionService()

@router.post("", response_model=InspectionCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_inspection(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    user = {
        "id": "OFF-8849-DL",
        "name": "Officer Rajesh Kumar",
        "email": "officer@labelsetu.gov.in",
        "role": "Officer",
        "designation": "Enforcement Official",
        "department": "Legal Metrology Department",
        "zone": "North Zone - Delhi HQ",
        "badgeNumber": "LM-ENF-2026-894",
    }

    allowed_content_types = ["image/jpeg", "image/png", "image/jpg", "application/octet-stream"]
    filename = file.filename or "upload.jpg"
    ext = os.path.splitext(filename)[1].lower()

    if ext not in [".jpg", ".jpeg", ".png"] and file.content_type not in allowed_content_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file format. Only JPG, JPEG, and PNG images are supported."
        )

    data = await file.read()
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty."
        )

    if len(data) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File exceeds maximum upload size of {settings.MAX_UPLOAD_SIZE_MB}MB."
        )

    try:
        inspection_id, file_path = inspection_service.start_inspection(
            file_bytes=data,
            filename=filename,
            content_type=file.content_type or "image/jpeg",
            inspector=user
        )
        # Schedule background pipeline
        background_tasks.add_task(
            inspection_service.process_inspection,
            inspection_id,
            file_path,
            user
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {"inspectionId": inspection_id}

@router.get("/{inspection_id}/status", response_model=InspectionStatus)
async def get_status(inspection_id: str):
    st = inspection_service.get_status(inspection_id)
    if not st:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inspection '{inspection_id}' not found."
        )
    return st

@router.get("/{inspection_id}")
async def get_inspection(inspection_id: str):
    insp = inspection_service.get_inspection(inspection_id)
    if not insp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inspection '{inspection_id}' not found."
        )
    return insp

@router.get("/{inspection_id}/image")
async def get_inspection(inspection_id: str):
    for ext in [".jpg", ".jpeg", ".png"]:
        path = os.path.join(settings.UPLOAD_DIR, f"{inspection_id}{ext}")
        if os.path.exists(path):
            media_type = "image/png" if ext == ".png" else "image/jpeg"
            return FileResponse(path, media_type=media_type)
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Image for inspection '{inspection_id}' not found."
    )

@router.get("/{inspection_id}/evidence", response_model=EvidenceResponse)
async def get_inspection(inspection_id: str):
    evidence = inspection_service.get_evidence(inspection_id)
    if not evidence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evidence for inspection '{inspection_id}' not found."
        )
    return evidence

@router.get("", response_model=HistoryResponse)
async def list_inspections(
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    date: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    user: dict = Depends(get_current_user)
):
    result = inspection_service.get_all_inspections(
        search=search,
        status=status,
        category=category,
        date=date,
        page=page,
        page_size=page_size
    )
    return result
