from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class Declaration(BaseModel):
    id: str
    fieldName: str
    extractedValue: Optional[str] = None
    confidence: float = 0.0
    status: str = "MISSING"  # COMPLIANT | NON-COMPLIANT | NEEDS REVIEW | MISSING
    finding: Optional[str] = None
    regionId: Optional[str] = None

class ComplianceCheck(BaseModel):
    id: str
    name: str
    status: str = "NEEDS REVIEW"  # COMPLIANT | NON-COMPLIANT | NEEDS REVIEW | MISSING
    confidence: float = 0.0
    explanation: str = ""
    regionId: Optional[str] = None

class PotentialViolation(BaseModel):
    id: str
    title: str
    status: str = "NEEDS REVIEW"  # NON-COMPLIANT | NEEDS REVIEW
    confidence: float = 0.0
    finding: str = ""
    evidence: Optional[str] = None
    extractedText: Optional[str] = None
    regionId: Optional[str] = None

class Region(BaseModel):
    id: str
    label: str
    field: str
    top: float
    left: float
    width: float
    height: float
    color: str = "#10B981"
    status: str = "COMPLIANT"
    extractedText: str = ""
    confidence: float = 0.0

class Product(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    subCategory: Optional[str] = None
    netQuantity: Optional[str] = None
    mrp: Optional[str] = None
    batchNo: Optional[str] = None
    packedDate: Optional[str] = None
    expiryDate: Optional[str] = None
    manufacturer: Optional[str] = None
    packer: Optional[str] = None
    importer: Optional[str] = None
    consumerCare: Optional[str] = None

class Overall(BaseModel):
    score: int = 0
    status: str = "NEEDS REVIEW"  # COMPLIANT | NON-COMPLIANT | NEEDS REVIEW | MISSING
    confidence: float = 0.0
    summaryText: str = ""
    assessmentType: str = "AUTOMATED"

class Review(BaseModel):
    reviewStatus: str = "PENDING"  # PENDING | DRAFT | FINALIZED
    finalAssessment: Optional[str] = None  # compliant | non_compliant | needs_review | None
    decisions: Dict[str, str] = Field(default_factory=dict)
    observations: str = ""
    reviewDate: Optional[str] = None

class Inspector(BaseModel):
    id: str
    name: str
    email: str
    role: str
    designation: str
    department: str
    zone: str
    badgeNumber: str

class Inspection(BaseModel):
    inspectionId: str
    date: str
    timestamp: float
    inspector: Inspector
    product: Product
    overall: Overall
    declarations: List[Declaration] = Field(default_factory=list)
    complianceChecks: List[ComplianceCheck] = Field(default_factory=list)
    potentialViolations: List[PotentialViolation] = Field(default_factory=list)
    regions: List[Region] = Field(default_factory=list)
    review: Review = Field(default_factory=Review)

class InspectionStatus(BaseModel):
    inspectionId: str
    status: str  # PROCESSING | COMPLETED | FAILED
    progress: int
    stage: str
    errorMessage: Optional[str] = None

class EvidenceBounds(BaseModel):
    x: float
    y: float
    width: float
    height: float

class EvidenceFinding(BaseModel):
    id: str
    label: str
    description: str
    bounds: EvidenceBounds

class EvidenceResponse(BaseModel):
    id: str
    imageUrl: str
    findings: List[EvidenceFinding]

class InspectionCreateResponse(BaseModel):
    inspectionId: str

class HistoryItem(BaseModel):
    inspectionId: str
    productName: str
    category: str
    categoryGroup: str
    manufacturer: str
    netQuantity: str
    mrp: str
    date: str
    rawDate: str
    officer: str
    complianceScore: int
    status: str
    hasReport: bool = True
    hasEvidence: bool = True

class HistoryResponse(BaseModel):
    items: List[HistoryItem]
    total: int
    page: int
    pageSize: int
