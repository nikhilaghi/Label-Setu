from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from app.auth.router import get_current_user, require_role
from .models import ComplaintCreateRequest, ComplaintUpdateRequest, ComplaintStatusRequest, ComplaintEvidenceRequest, Complaint
from .service import ComplaintService

router = APIRouter(prefix="/api/complaints", tags=["complaints"])
service = ComplaintService()

@router.get("", response_model=list[Complaint])
async def list_complaints(status: Optional[str] = Query(None), search: Optional[str] = Query(None), user: dict = Depends(get_current_user)):
    customer_id = user["id"] if user["role"].lower() == "customer" else None
    return service.list(customer_id=customer_id, status=status, search=search)

@router.post("", response_model=Complaint, status_code=201)
async def create_complaint(data: ComplaintCreateRequest, user: dict = Depends(require_role("Customer"))):
    return service.create(data.model_dump(), user)

@router.get("/notifications")
async def notifications(user: dict = Depends(get_current_user)):
    recipient = "customer" if user["role"].lower() == "customer" else "officer"
    return service.notifications(recipient)

@router.get("/{complaint_id}", response_model=Complaint)
async def get_complaint(complaint_id: str, user: dict = Depends(get_current_user)):
    complaint = service.get(complaint_id)
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    if user["role"].lower() == "customer" and complaint.get("customerId") != user["id"]:
        raise HTTPException(status_code=403, detail="You cannot access this complaint")
    return complaint

@router.put("/{complaint_id}", response_model=Complaint)
async def update_complaint(complaint_id: str, data: ComplaintUpdateRequest, user: dict = Depends(require_role("Officer"))):
    complaint = service.update(complaint_id, data.model_dump(exclude_none=True))
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    return complaint

@router.post("/{complaint_id}/status", response_model=Complaint)
async def update_status(complaint_id: str, data: ComplaintStatusRequest, user: dict = Depends(require_role("Officer"))):
    try:
        complaint = service.update_status(complaint_id, data.status, data.officerRemarks, data.officerDecision)
        if not complaint:
            raise HTTPException(status_code=404, detail="Complaint not found")
        return complaint
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{complaint_id}/evidence", response_model=Complaint)
async def add_evidence(complaint_id: str, data: ComplaintEvidenceRequest, user: dict = Depends(require_role("Customer"))):
    try:
        complaint = service.add_evidence(complaint_id, data.model_dump(), user)
        if not complaint:
            raise HTTPException(status_code=404, detail="Complaint not found")
        return complaint
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

@router.delete("/{complaint_id}")
async def delete_complaint(complaint_id: str, user: dict = Depends(require_role("Officer"))):
    complaint = service.get(complaint_id)
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    from .repository import delete_complaints
    delete_complaints([complaint_id])
    return {"message": "Complaint deleted successfully", "complaintId": complaint_id}
