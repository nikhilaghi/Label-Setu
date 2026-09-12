from typing import Dict, Any, List
from .rules import (
    ManufacturingDetailsRule,
    NetQuantityRule,
    MRPRule,
    DateInformationRule,
    ConsumerCareRule,
    FontSizeRule,
)

class ComplianceEngine:
    def __init__(self):
        self.rules = [
            ManufacturingDetailsRule(),
            NetQuantityRule(),
            MRPRule(),
            DateInformationRule(),
            ConsumerCareRule(),
            FontSizeRule(),
        ]

    def evaluate(self, extracted: Dict[str, Any], regions: List[Dict[str, Any]]) -> Dict[str, Any]:
        checks = []
        for rule in self.rules:
            check = rule.evaluate(extracted, regions)
            checks.append(check)

        # Exact Score Map per requirement 9:
        # COMPLIANT = 100, NEEDS REVIEW = 60, NON-COMPLIANT = 0, MISSING = 0
        score_map = {
    "COMPLIANT": 100,
    "NEEDS REVIEW": 75,
    "NON-COMPLIANT": 0,
    "MISSING": 0
}

        check_scores = [score_map.get(c["status"], 0) for c in checks]
        # Overall score is exact rounded average of all 6 checks
        overall_score = round(sum(check_scores) / len(check_scores)) if check_scores else 0

        # Overall status determination:
        statuses = [c["status"] for c in checks]
        if "NON-COMPLIANT" in statuses:
            overall_status = "NON-COMPLIANT"
        elif "NEEDS REVIEW" in statuses or "MISSING" in statuses:
            overall_status = "NEEDS REVIEW"
        else:
            overall_status = "COMPLIANT"

        avg_conf = sum(c["confidence"] for c in checks) / len(checks) if checks else 0.85

        summary_parts = []
        compliant_count = sum(1 for s in statuses if s == "COMPLIANT")
        review_count = sum(1 for s in statuses if s == "NEEDS REVIEW")
        non_compliant_count = sum(1 for s in statuses if s == "NON-COMPLIANT")

        summary_parts.append(
            f"Evaluated {len(checks)} statutory Legal Metrology rules: "
            f"{compliant_count} Compliant, {review_count} Needs Review, {non_compliant_count} Non-Compliant."
        )

        overall = {
            "score": int(overall_score),
            "status": overall_status,
            "confidence": round(avg_conf, 2),
            "summaryText": " ".join(summary_parts),
            "assessmentType": "AUTOMATED"
        }

        # Build Potential Violations for NON-COMPLIANT or material NEEDS REVIEW
        violations = []
        for check in checks:
            if check["status"] in ["NON-COMPLIANT", "NEEDS REVIEW"]:
                # Attempt to extract text from matching region
                region_id = check.get("regionId")
                extracted_text = None
                evidence_desc = check["explanation"]

                if region_id:
                    for reg in regions:
                        if reg.get("id") == region_id:
                            extracted_text = reg.get("extractedText")
                            break

                violation = {
                    "id": f"viol_{check['id']}",
                    "title": check["name"],
                    "status": check["status"],
                    "confidence": check["confidence"],
                    "finding": check["explanation"],
                    "evidence": evidence_desc,
                    "extractedText": extracted_text,
                    "regionId": region_id
                }
                violations.append(violation)

        return {
            "checks": checks,
            "overall": overall,
            "violations": violations
        }
