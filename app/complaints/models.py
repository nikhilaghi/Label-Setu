from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

COMPLAINT_STATUSES = {
    "SUBMITTED",
    "UNDER_REVIEW",
    "ADDITIONAL_EVIDENCE_REQUIRED",
    "RESOLVED",
    "REJECTED",
}

class ComplaintCreateRequest(BaseModel):
    productId: Optional[str] = None
    productName: str = "Packaged Commodity"
    inspectionId: Optional[str] = None
    category: str = "Consumer Care Issue"
    description: str = ""
    image: Optional[str] = None
    imageUrl: Optional[str] = None
    aiAnalysis: Dict[str, Any] = Field(default_factory=dict)
    eligibility: str = "ELIGIBLE"
    additionalEvidence: List[Dict[str, Any]] = Field(default_factory=list)

class ComplaintUpdateRequest(BaseModel):
    officerRemarks: Optional[str] = None
    officerDecision: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None

class ComplaintStatusRequest(BaseModel):
    status: str
    officerRemarks: str = ""
    officerDecision: str = ""

class ComplaintEvidenceRequest(BaseModel):
    name: str = "Additional Evidence Document"
    url: Optional[str] = None
    notes: str = "Submitted by customer in response to officer request."

class Notification(BaseModel):
    id: str
    recipient: str
    title: str
    message: str
    complaintId: Optional[str] = None
    type: str = "info"
    product: Optional[str] = None
    unread: bool = True
    createdAt: str

class Complaint(BaseModel):
    complaintId: str
    id: str
    customerId: str
    customerName: str
    customerEmail: str
    productId: str
    productName: str
    product: str
    inspectionId: Optional[str] = None
    category: str
    description: str
    image: Optional[str] = None
    imageUrl: Optional[str] = None
    aiAnalysis: Dict[str, Any] = Field(default_factory=dict)
    eligibility: str = "ELIGIBLE"
    status: str = "SUBMITTED"
    officerRemarks: str = ""
    officerDecision: str = ""
    additionalEvidence: List[Dict[str, Any]] = Field(default_factory=list)
    submittedAt: str
    updatedAt: str
    date: str
    timeline: List[Dict[str, Any]] = Field(default_factory=list)
