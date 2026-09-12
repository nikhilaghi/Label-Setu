from pydantic import BaseModel, Field
from typing import Dict, Optional

class ReviewSaveRequest(BaseModel):
    reviewStatus: str = "DRAFT"
    finalAssessment: Optional[str] = None  # compliant | further_review | non_compliant
    decisions: Dict[str, str] = Field(default_factory=dict)
    observations: Dict[str, str] = Field(default_factory=dict)
    checklist: Dict[str, bool] = Field(default_factory=dict)
    reviewDate: Optional[str] = None

class ReviewSubmitRequest(BaseModel):
    reviewStatus: str = "REVIEWED"
    finalAssessment: str  # compliant | further_review | non_compliant
    decisions: Dict[str, str] = Field(default_factory=dict)
    observations: Dict[str, str] = Field(default_factory=dict)
    checklist: Dict[str, bool] = Field(default_factory=dict)
