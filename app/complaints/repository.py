from typing import Dict, List, Optional
from app.storage.memory import MemoryStorage

storage = MemoryStorage()

INITIAL_COMPLAINTS = [
    {
        "complaintId": "CMP-2026-0001", "id": "CMP-2026-0001",
        "customerId": "CUST-2026-001", "customerName": "Authorized Business Representative",
        "customerEmail": "customer@labelsetu.gov.in", "productId": "PRD-001",
        "productName": "ABC Premium Rice", "product": "ABC Premium Rice", "inspectionId": "LM-2026-00129",
        "category": "Consumer Care Issue",
        "description": "Consumer care contact telephone number appears truncated or masked on the rear packaging panel.",
        "image": "", "imageUrl": "",
        "aiAnalysis": {"issueDetected": True, "confidence": 88, "issue": "Consumer care contact information appears incomplete."},
        "eligibility": "ELIGIBLE", "status": "SUBMITTED", "officerRemarks": "", "officerDecision": "",
        "additionalEvidence": [], "submittedAt": "2026-09-09T09:30:00.000Z", "updatedAt": "2026-09-09T09:30:00.000Z",
        "date": "09 Sep 2026",
        "timeline": [{"status": "SUBMITTED", "title": "Complaint Submitted", "date": "09 Sep 2026, 09:30 AM", "note": "Customer submitted grievance with AI preliminary verification.", "by": "Customer"}],
    },
    {
        "complaintId": "CMP-2026-0002", "id": "CMP-2026-0002",
        "customerId": "CUST-2026-002", "customerName": "Rahul Verma", "customerEmail": "customer2@labelsetu.gov.in",
        "productId": "PRD-002", "productName": "XYZ Premium Atta", "product": "XYZ Premium Atta", "inspectionId": "LM-2026-00094",
        "category": "Missing Information", "description": "MRP declaration and inclusive of all taxes wording is smudged and requires regulatory verification.",
        "image": "", "imageUrl": "", "aiAnalysis": {"issueDetected": True, "confidence": 91, "issue": "MRP declaration requires verification."},
        "eligibility": "ELIGIBLE", "status": "UNDER_REVIEW", "officerRemarks": "Enforcement review initiated by Legal Metrology team.", "officerDecision": "",
        "additionalEvidence": [], "submittedAt": "2026-09-08T14:15:00.000Z", "updatedAt": "2026-09-09T10:00:00.000Z", "date": "08 Sep 2026",
        "timeline": [
            {"status": "SUBMITTED", "title": "Complaint Submitted", "date": "08 Sep 2026, 02:15 PM", "note": "Customer submitted grievance.", "by": "Customer"},
            {"status": "UNDER_REVIEW", "title": "Under Officer Review", "date": "09 Sep 2026, 10:00 AM", "note": "Enforcement official started label compliance review.", "by": "Officer"},
        ],
    },
    {
        "complaintId": "CMP-2026-0003", "id": "CMP-2026-0003",
        "customerId": "CUST-2026-003", "customerName": "Anita Sharma", "customerEmail": "customer3@labelsetu.gov.in",
        "productId": "PRD-003", "productName": "Fresh Sugar", "product": "Fresh Sugar", "inspectionId": "LM-2026-00052",
        "category": "Incorrect Quantity", "description": "Reported net weight symbol formatting issue without sufficient high-resolution packaging proof.",
        "image": "", "imageUrl": "", "aiAnalysis": {"issueDetected": False, "confidence": 72, "issue": "No sufficient evidence."},
        "eligibility": "REJECTED", "status": "REJECTED", "officerRemarks": "Insufficient evidence provided to establish statutory declaration breach.", "officerDecision": "Complaint rejected due to lack of verifiable evidence.",
        "additionalEvidence": [], "submittedAt": "2026-09-07T11:20:00.000Z", "updatedAt": "2026-09-08T09:45:00.000Z", "date": "07 Sep 2026",
        "timeline": [
            {"status": "SUBMITTED", "title": "Complaint Submitted", "date": "07 Sep 2026, 11:20 AM", "note": "Customer submitted grievance.", "by": "Customer"},
            {"status": "UNDER_REVIEW", "title": "Under Officer Review", "date": "07 Sep 2026, 04:00 PM", "note": "Enforcement official started review.", "by": "Officer"},
            {"status": "REJECTED", "title": "Complaint Rejected", "date": "08 Sep 2026, 09:45 AM", "note": "Insufficient evidence to validate the reported issue.", "by": "Officer"},
        ],
    },
]


def initialize():
    if storage.get("complaints") is None:
        storage.save("complaints", INITIAL_COMPLAINTS)
    if storage.get("notifications") is None:
        storage.save("notifications", [])


def list_complaints() -> List[dict]:
    initialize()
    return storage.get("complaints") or []


def get_complaint(complaint_id: str) -> Optional[dict]:
    normalized = complaint_id.strip().upper()
    return next((c for c in list_complaints() if c.get("complaintId", "").upper() == normalized or c.get("id", "").upper() == normalized), None)


def save_complaint(complaint: dict):
    items = list_complaints()
    for idx, item in enumerate(items):
        if item.get("complaintId") == complaint.get("complaintId"):
            items[idx] = complaint
            break
    else:
        items.insert(0, complaint)
    storage.save("complaints", items)
    return complaint


def delete_complaints(ids: List[str]):
    normalized = {i.upper() for i in ids}
    items = [c for c in list_complaints() if c.get("complaintId", "").upper() not in normalized]
    storage.save("complaints", items)
    return items


def list_notifications(recipient: str) -> List[dict]:
    initialize()
    return [n for n in (storage.get("notifications") or []) if n.get("recipient") == recipient]


def save_notification(notification: dict):
    items = storage.get("notifications") or []
    items.insert(0, notification)
    storage.save("notifications", items)
    return notification
