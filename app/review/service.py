from datetime import datetime, timezone
from typing import Optional
from app.inspections.repository import get_inspection, save_inspection

VALID_ASSESSMENTS = {"compliant", "further_review", "non_compliant"}

class ReviewService:
    def get_review(self, inspection_id: str) -> Optional[dict]:
        insp = get_inspection(inspection_id)
        if not insp:
            return None
        return insp.get("review", self._empty_review())

    @staticmethod
    def _empty_review() -> dict:
        return {
            "reviewStatus": "PENDING",
            "finalAssessment": None,
            "decisions": {},
            "observations": {},
            "checklist": {},
            "reviewDate": None,
        }

    def save_review(self, inspection_id: str, review_data: dict) -> Optional[dict]:
        insp = get_inspection(inspection_id)
        if not insp:
            return None
        current_review = insp.get("review", {})
        if current_review.get("reviewStatus") == "REVIEWED":
            raise ValueError("Inspection review has been finalized and locked against draft modifications.")

        final_assessment = review_data.get("finalAssessment")
        if final_assessment and final_assessment not in VALID_ASSESSMENTS:
            raise ValueError("Invalid finalAssessment. Use compliant, further_review, or non_compliant.")

        insp["review"] = {
            "reviewStatus": "DRAFT",
            "finalAssessment": final_assessment,
            "decisions": review_data.get("decisions", {}),
            "observations": review_data.get("observations", {}),
            "checklist": review_data.get("checklist", {}),
            "reviewDate": review_data.get("reviewDate") or datetime.now(timezone.utc).isoformat(),
        }
        save_inspection(insp)
        return insp

    def submit_review(self, inspection_id: str, review_data: dict) -> Optional[dict]:
        insp = get_inspection(inspection_id)
        if not insp:
            return None
        current_review = insp.get("review", {})
        if current_review.get("reviewStatus") == "REVIEWED":
            raise ValueError("Inspection review has already been finalized and locked.")

        final_assessment = str(review_data.get("finalAssessment", "")).lower()
        if final_assessment not in VALID_ASSESSMENTS:
            raise ValueError("A valid finalAssessment is required: compliant, further_review, or non_compliant.")

        status_map = {
            "compliant": ("COMPLIANT", max(insp.get("overall", {}).get("score", 0), 100)),
            "further_review": ("NEEDS REVIEW", 60),
            "non_compliant": ("NON-COMPLIANT", min(insp.get("overall", {}).get("score", 100), 40)),
        }
        final_status, final_score = status_map[final_assessment]

        insp["review"] = {
            "reviewStatus": "REVIEWED",
            "finalAssessment": final_assessment,
            "decisions": review_data.get("decisions", {}),
            "observations": review_data.get("observations", {}),
            "checklist": review_data.get("checklist", {}),
            "reviewDate": datetime.now(timezone.utc).isoformat(),
        }
        insp["overall"]["status"] = final_status
        insp["overall"]["score"] = final_score
        insp["overall"]["assessmentType"] = "OFFICER_FINALIZED"
        base_summary = insp["overall"].get("summaryText", "").strip()
        suffix = f" Final assessment completed by enforcement officer ({final_status})."
        insp["overall"]["summaryText"] = base_summary + suffix if suffix.strip() not in base_summary else base_summary

        save_inspection(insp)
        return insp
