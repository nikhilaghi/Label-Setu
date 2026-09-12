from pydantic import BaseModel, Field
from typing import Optional

class Profile(BaseModel):
    fullName: str = "Officer Rajesh Kumar"
    role: str = "Officer"
    department: str = "Legal Metrology Department"
    email: str = "officer@labelsetu.gov.in"
    phone: str = "+91-9876543210"
    employeeId: str = "OFF-8849-DL"

class InspectionPreferences(BaseModel):
    autoSave: bool = True
    showConfidenceScores: bool = True
    showEvidenceHighlights: bool = True
    requireOfficerReview: bool = False
    defaultReportFormat: str = "PDF"
    defaultCategory: str = "Packaged Food & Beverages"

class Notifications(BaseModel):
    inspectionCompleted: bool = True
    officerReviewRequired: bool = True
    reportGenerated: bool = True
    violationDetected: bool = True
    systemUpdates: bool = False

class Appearance(BaseModel):
    theme: str = "light"
    density: str = "comfortable"
    language: str = "en"

class SettingsModel(BaseModel):
    profile: Profile = Field(default_factory=Profile)
    inspectionPreferences: InspectionPreferences = Field(default_factory=InspectionPreferences)
    notifications: Notifications = Field(default_factory=Notifications)
    appearance: Appearance = Field(default_factory=Appearance)
