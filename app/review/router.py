from fastapi import APIRouter, Depends, HTTPException, status
from app.auth.router import get_current_user, require_role
from app.inspections.repository import get_inspection
from .service import ReviewService
from .models import ReviewSaveRequest, ReviewSubmitRequest

router = APIRouter(prefix="/api/inspections/{inspection_id}/review", tags=["review"])
review_service = ReviewService()

@router.get("")
async def get_review(inspection_id: str, user: dict = Depends(get_current_user)):
    review = review_service.get_review(inspection_id)
    if review is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Inspection '{inspection_id}' not found.")
    return review

@router.put("")
async def save_review(inspection_id: str, data: ReviewSaveRequest, user: dict = Depends(require_role("Officer"))):
    try:
        insp = review_service.save_review(inspection_id, data.model_dump())
        if not insp:
            raise HTTPException(status_code=404, detail=f"Inspection '{inspection_id}' not found.")
        return {"message": "Review draft saved successfully", "inspectionId": inspection_id, "review": insp["review"]}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/submit")
async def submit_review(inspection_id: str, data: ReviewSubmitRequest, user: dict = Depends(require_role("Officer"))):
    try:
        insp = review_service.submit_review(inspection_id, data.model_dump())
        if not insp:
            raise HTTPException(status_code=404, detail=f"Inspection '{inspection_id}' not found.")
        return {"message": "Officer review finalized successfully", "inspectionId": inspection_id, "review": insp["review"], "inspection": insp}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
