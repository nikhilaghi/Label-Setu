from datetime import datetime, timezone
from typing import List, Optional
from .repository import get_complaint, list_complaints, save_complaint, delete_complaints, save_notification, list_notifications

class ComplaintService:
    def list(self, customer_id: Optional[str] = None, status: Optional[str] = None, search: Optional[str] = None) -> List[dict]:
        items = list_complaints()
        if customer_id:
            items = [c for c in items if c.get("customerId") == customer_id]
        if status:
            items = [c for c in items if c.get("status", "").upper() == status.upper()]
        if search:
            s = search.lower().strip()
            items = [c for c in items if any(s in str(c.get(k, "")).lower() for k in ("complaintId", "productName", "category", "description"))]
        return sorted(items, key=lambda c: c.get("updatedAt", ""), reverse=True)

    def get(self, complaint_id: str) -> Optional[dict]:
        return get_complaint(complaint_id)

    def create(self, data: dict, customer: dict) -> dict:
        existing = list_complaints()
        nums = []
        for item in existing:
            cid = item.get("complaintId", "")
            try:
                nums.append(int(cid.split("-")[-1]))
            except Exception:
                pass
        next_num = max(nums, default=0) + 1
        complaint_id = f"CMP-{datetime.now(timezone.utc).year}-{next_num:04d}"
        now = datetime.now(timezone.utc).isoformat()
        short_date = datetime.now().strftime("%d %b %Y")
        short_time = datetime.now().strftime("%d %b %Y, %I:%M %p")
        complaint = {
            "complaintId": complaint_id,
            "id": complaint_id,
            "customerId": customer["id"],
            "customerName": customer.get("name", "Customer"),
            "customerEmail": customer.get("email", ""),
            "productId": data.get("productId") or f"PRD-{next_num:04d}",
            "productName": data.get("productName") or "Packaged Commodity",
            "product": data.get("productName") or "Packaged Commodity",
            "inspectionId": data.get("inspectionId"),
            "category": data.get("category") or "Consumer Care Issue",
            "description": data.get("description", ""),
            "image": data.get("image") or data.get("imageUrl"),
            "imageUrl": data.get("imageUrl") or data.get("image"),
            "aiAnalysis": data.get("aiAnalysis") or {"issueDetected": True, "confidence": 80, "issue": "Preliminary review required."},
            "eligibility": data.get("eligibility", "ELIGIBLE"),
            "status": "SUBMITTED",
            "officerRemarks": "",
            "officerDecision": "",
            "additionalEvidence": data.get("additionalEvidence", []),
            "submittedAt": now,
            "updatedAt": now,
            "date": short_date,
            "timeline": [{"status": "SUBMITTED", "title": "Complaint Submitted", "date": short_time, "note": "Grievance submitted by Customer for enforcement review.", "by": "Customer"}],
        }
        save_complaint(complaint)
        self._notify("officer", "New Complaint Received", f"Customer lodged complaint {complaint_id} for product {complaint['productName']}.", complaint_id, "warning", complaint["productName"])
        return complaint

    def update(self, complaint_id: str, updates: dict) -> Optional[dict]:
        complaint = get_complaint(complaint_id)
        if not complaint:
            return None
        complaint.update({k: v for k, v in updates.items() if v is not None})
        complaint["updatedAt"] = datetime.now(timezone.utc).isoformat()
        return save_complaint(complaint)

    def update_status(self, complaint_id: str, new_status: str, remarks: str = "", decision: str = "") -> Optional[dict]:
        new_status = new_status.upper().strip()
        if new_status not in {"SUBMITTED", "UNDER_REVIEW", "ADDITIONAL_EVIDENCE_REQUIRED", "RESOLVED", "REJECTED"}:
            raise ValueError("Invalid complaint status.")
        complaint = get_complaint(complaint_id)
        if not complaint:
            return None
        now = datetime.now(timezone.utc)
        date_text = now.strftime("%d %b %Y, %I:%M %p")
        titles = {
            "UNDER_REVIEW": "Under Officer Review",
            "ADDITIONAL_EVIDENCE_REQUIRED": "Additional Evidence Required",
            "RESOLVED": "Complaint Validated & Resolved",
            "REJECTED": "Complaint Rejected",
            "SUBMITTED": "Status Updated",
        }
        notes = remarks or {
            "UNDER_REVIEW": "Enforcement official initiated preliminary label verification.",
            "ADDITIONAL_EVIDENCE_REQUIRED": "Additional evidence requested by officer.",
            "RESOLVED": "Complaint verified and resolved by the enforcement team.",
            "REJECTED": "Complaint rejected following verification.",
            "SUBMITTED": "Status updated by officer.",
        }[new_status]
        complaint["status"] = new_status
        complaint["officerRemarks"] = remarks or complaint.get("officerRemarks", "")
        complaint["officerDecision"] = decision or complaint.get("officerDecision", "")
        complaint.setdefault("timeline", []).append({"status": new_status, "title": titles[new_status], "date": date_text, "note": notes, "by": "Officer"})
        complaint["updatedAt"] = now.isoformat()
        saved = save_complaint(complaint)

        messages = {
            "UNDER_REVIEW": ("Complaint Under Review", f"Your complaint {complaint_id} is now being reviewed by an enforcement official.", "info"),
            "ADDITIONAL_EVIDENCE_REQUIRED": ("Additional Evidence Required", f"Officer requested additional evidence for {complaint_id}: {remarks or 'Please provide supporting evidence.'}", "warning"),
            "RESOLVED": ("Complaint Resolved", f"Your complaint {complaint_id} has been validated and resolved by the enforcement team.", "success"),
            "REJECTED": ("Complaint Rejected", f"Your complaint {complaint_id} has been rejected. Remarks: {remarks or 'Insufficient evidence.'}", "error"),
        }
        if new_status in messages:
            title, message, typ = messages[new_status]
            self._notify("customer", title, message, complaint_id, typ, complaint.get("productName"))
        return saved

    def add_evidence(self, complaint_id: str, evidence: dict, customer: dict) -> Optional[dict]:
        complaint = get_complaint(complaint_id)
        if not complaint:
            return None
        if complaint.get("customerId") != customer.get("id"):
            raise PermissionError("Complaint does not belong to the current customer.")
        now = datetime.now(timezone.utc)
        evidence_item = {
            "id": f"EVD-{int(now.timestamp() * 1000)}",
            "url": evidence.get("url"),
            "name": evidence.get("name", "Additional Evidence Document"),
            "notes": evidence.get("notes", "Submitted by customer in response to officer request."),
            "uploadedAt": now.isoformat(),
            "date": now.strftime("%d %b %Y, %I:%M %p"),
        }
        complaint.setdefault("additionalEvidence", []).append(evidence_item)
        complaint["status"] = "UNDER_REVIEW"
        complaint.setdefault("timeline", []).append({"status": "UNDER_REVIEW", "title": "Additional Evidence Submitted", "date": evidence_item["date"], "note": f"Customer uploaded supplementary evidence ({evidence_item['name']}).", "by": "Customer"})
        complaint["updatedAt"] = now.isoformat()
        return save_complaint(complaint)

    def delete(self, ids: List[str], officer: dict):
        return delete_complaints(ids)

    @staticmethod
    def _notify(recipient: str, title: str, message: str, complaint_id: str, typ: str, product: str):
        now = datetime.now(timezone.utc).isoformat()
        save_notification({"id": f"NOTIF-{int(datetime.now().timestamp()*1000)}", "recipient": recipient, "title": title, "message": message, "complaintId": complaint_id, "type": typ, "product": product, "unread": True, "createdAt": now})

    def notifications(self, recipient: str):
        return sorted(list_notifications(recipient), key=lambda n: n.get("createdAt", ""), reverse=True)
