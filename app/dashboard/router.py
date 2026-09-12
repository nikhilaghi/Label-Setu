from fastapi import APIRouter, Depends
from typing import List, Dict, Any
from app.auth.router import get_current_user
from app.inspections.repository import get_all_inspection_ids, get_inspection

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

@router.get("/summary")
async def get_dashboard_summary(user: dict = Depends(get_current_user)):
    ids = get_all_inspection_ids()
    inspections = []

    for iid in ids:
        insp = get_inspection(iid)
        if insp:
            inspections.append(insp)

    # Sort inspections descending by timestamp (Rule 14)
    inspections.sort(key=lambda x: x.get("timestamp", 0), reverse=True)

    total_inspections = len(inspections)
    compliant_count = sum(1 for i in inspections if i.get("overall", {}).get("status") == "COMPLIANT")
    non_compliant_count = sum(1 for i in inspections if i.get("overall", {}).get("status") == "NON-COMPLIANT")
    needs_review_count = sum(1 for i in inspections if i.get("overall", {}).get("status") in ["NEEDS REVIEW", "MISSING"])
    
    avg_score = (
        round(sum(i.get("overall", {}).get("score", 0) for i in inspections) / total_inspections, 1)
        if total_inspections > 0
        else 0.0
    )

    stats = [
        {
            "id": "total",
            "title": "Total Inspections",
            "value": total_inspections,
            "change": "+12%",
            "trend": "up",
            "color": "#4CAF50",
            "icon": "clipboard-list",
            "description": "All submitted inspections"
        },
        {
            "id": "compliant",
            "title": "Compliant",
            "value": compliant_count,
            "change": "+8%",
            "trend": "up",
            "color": "#2196F3",
            "icon": "check-circle",
            "description": "Fully compliant labels"
        },
        {
            "id": "non_compliant",
            "title": "Non-Compliant",
            "value": non_compliant_count,
            "change": "-5%",
            "trend": "down",
            "color": "#F44336",
            "icon": "alert-circle",
            "description": "Requires enforcement"
        },
        {
            "id": "needs_review",
            "title": "Needs Review",
            "value": needs_review_count,
            "change": "+3%",
            "trend": "up",
            "color": "#FF9800",
            "icon": "eye",
            "description": "Awaiting officer decision"
        },
        {
            "id": "avg_score",
            "title": "Avg Score",
            "value": avg_score,
            "change": "+2%",
            "trend": "up",
            "color": "#9C27B0",
            "icon": "percent",
            "description": "Average compliance score"
        }
    ]

    compliance_chart = [
        {
            "name": "Compliant",
            "value": compliant_count,
            "count": compliant_count,
            "color": "#10B981"
        },
        {
            "name": "Needs Review",
            "value": needs_review_count,
            "count": needs_review_count,
            "color": "#F59E0B"
        },
        {
            "name": "Non-Compliant",
            "value": non_compliant_count,
            "count": non_compliant_count,
            "color": "#EF4444"
        }
    ]

    recent_inspections = []
    for insp in inspections[:5]:  # Top 5 newest
        prod = insp.get("product", {})
        overall = insp.get("overall", {})
        raw_date = insp.get("date", "")
        formatted_date = raw_date[:10] if len(raw_date) >= 10 else raw_date

        recent_inspections.append({
            "id": insp.get("inspectionId"),
            "product": prod.get("name") or "Packaged Commodity",
            "category": prod.get("category") or "General",
            "date": formatted_date,
            "status": overall.get("status", "NEEDS REVIEW"),
            "complianceScore": overall.get("score", 0),
            "manufacturer": prod.get("manufacturer") or "Not Specified",
            "batchNo": prod.get("batchNo") or "N/A"
        })

    return {
        "stats": stats,
        "complianceChart": compliance_chart,
        "recentInspections": recent_inspections
    }
