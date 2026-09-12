from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from app.auth.router import require_role
from app.inspections.service import InspectionService

router = APIRouter(prefix="/api/customer", tags=["customer"])
inspection_service = InspectionService()

@router.get("/inspections")
async def customer_inspections(user: dict = Depends(require_role("Customer")), page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=100), search: Optional[str] = None, status: Optional[str] = None):
    result = inspection_service.get_all_inspections(search=search, status=status, page=page, page_size=page_size, customer_id=user["id"])
    return result

@router.get("/inspections/{inspection_id}")
async def customer_inspection_detail(inspection_id: str, user: dict = Depends(require_role("Customer"))):
    inspection = inspection_service.get_inspection(inspection_id)
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")
    if inspection.get("customerId") != user["id"]:
        raise HTTPException(status_code=403, detail="You cannot access this inspection")

        raise HTTPException(status_code=404, detail="Inspection not found")
    return inspection

@router.get("/products")
async def customer_products(user: dict = Depends(require_role("Customer"))):
    result = inspection_service.get_all_inspections(page=1, page_size=100, customer_id=user["id"])
    seen = {}
    for item in result["items"]:
        key = item["productName"]
        if key not in seen:
            seen[key] = {
                "id": f"prod-{len(seen)+1:03d}",
                "name": key,
                "category": item["category"],
                "inspectionId": item["inspectionId"],
                "score": item["complianceScore"],
                "status": item["status"],
                "updatedAt": item["date"],
            }
    return list(seen.values())

@router.get("/reports")
async def customer_reports(user: dict = Depends(require_role("Customer"))):
    result = inspection_service.get_all_inspections(page=1, page_size=100, customer_id=user["id"])
    reports = []
    for item in result["items"]:
        reports.append({
            "id": f"rep-{item['inspectionId']}",
            "name": f"LABEL_SETU_Inspection_{item['inspectionId']}.pdf",
            "inspectionId": item["inspectionId"],
            "product": item["productName"],
            "date": item["date"],
            "status": "Available" if item.get("hasReport") else "Pending",
            "size": "Generated on demand",
        })
    return reports
