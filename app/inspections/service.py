import os
from .repository import (
    save_inspection,
    get_inspection,
    save_status,
    get_status,
    inspection_repository,
)
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from app.config import settings
from .repository import (
    save_inspection,
    get_inspection,
    save_status,
    get_status,
    add_inspection_id,
    get_all_inspection_ids
)
from app.compliance.engine import ComplianceEngine
from .ocr_pipeline import OCRPipeline

class InspectionService:
    def __init__(self):
        self.ocr_pipeline = OCRPipeline()
        self.compliance_engine = ComplianceEngine()

    def _generate_id(self) -> str:
        return inspection_repository.next_id()

    def save_file(self, data: bytes, filename: str, content_type: str, inspection_id: str) -> str:
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        ext = os.path.splitext(filename)[1].lower()
        if ext not in [".jpg", ".jpeg", ".png"]:
            if "png" in content_type:
                ext = ".png"
            else:
                ext = ".jpg"

        if len(data) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
            raise ValueError(f"File size exceeds maximum limit of {settings.MAX_UPLOAD_SIZE_MB}MB")

        file_path = os.path.join(settings.UPLOAD_DIR, f"{inspection_id}{ext}")
        with open(file_path, "wb") as f:
            f.write(data)
        return file_path

    def start_inspection(self, file_bytes: bytes, filename: str, content_type: str, inspector: dict) -> tuple[str, str]:
        inspection_id = self._generate_id()
        file_path = self.save_file(file_bytes, filename, content_type, inspection_id)

        initial_status = {
            "inspectionId": inspection_id,
            "status": "PROCESSING",
            "progress": 5,
            "stage": "uploaded",
            "errorMessage": None
        }
        save_status(initial_status)
        add_inspection_id(inspection_id)
        return inspection_id, file_path

    def process_inspection(self, inspection_id: str, file_path: str, inspector: dict) -> None:
        try:
            self._update_status(inspection_id, "PROCESSING", 20, "OCR scanning label")

            # Run OCR
            ocr_data = self.ocr_pipeline.perform_ocr(file_path)

            self._update_status(inspection_id, "PROCESSING", 50, "Extracting statutory declarations")

            # Extract fields and entities
            extracted = self.ocr_pipeline.extract_fields(ocr_data["text"], ocr_data)

            # Map regions
            regions = self.ocr_pipeline.create_regions(ocr_data, extracted)

            self._update_status(inspection_id, "PROCESSING", 80, "Evaluating compliance rules")

            # Evaluate compliance
            compliance_result = self.compliance_engine.evaluate(extracted, regions)

            # Build full inspection document
            inspection = self._build_inspection(
                inspection_id=inspection_id,
                file_path=file_path,
                inspector=inspector,
                extracted=extracted,
                compliance=compliance_result,
                regions=regions,
                ocr_data=ocr_data
            )

            save_inspection(inspection)
            self._update_status(inspection_id, "COMPLETED", 100, "completed")
        except Exception as e:
            self._update_status(inspection_id, "FAILED", 100, "failed", errorMessage=str(e))

    def _update_status(self, inspection_id: str, status: str, progress: int, stage: str, errorMessage: Optional[str] = None) -> None:
        existing = get_status(inspection_id) or {"inspectionId": inspection_id}
        existing.update({
            "status": status,
            "progress": progress,
            "stage": stage,
            "errorMessage": errorMessage
        })
        save_status(existing)

    def _build_inspection(
        self,
        inspection_id: str,
        file_path: str,
        inspector: dict,
        extracted: dict,
        compliance: dict,
        regions: list,
        ocr_data: dict
    ) -> dict:
        now = datetime.now(timezone.utc)
        iso_date = now.isoformat()
        ts = now.timestamp()

        inspector_info = {
            "id": inspector.get("id", "OFF-8849-DL"),
            "name": inspector.get("name", "Officer Rajesh Kumar"),
            "email": inspector.get("email", "officer@labelsetu.gov.in"),
            "role": inspector.get("role", "Officer"),
            "designation": inspector.get("designation", "Enforcement Official"),
            "department": inspector.get("department", "Legal Metrology Department"),
            "zone": inspector.get("zone", "North Zone - Delhi HQ"),
            "badgeNumber": inspector.get("badgeNumber", "LM-ENF-2026-894")
        }

        # Initial clean review object (Rule 4)
        review_obj = {
            "reviewStatus": "PENDING",
            "finalAssessment": None,
            "decisions": {},
            "observations": "",
            "reviewDate": None
        }

        return {
            "inspectionId": inspection_id,
            "date": iso_date,
            "customerId": inspector.get("id") if inspector.get("role", "").lower() == "customer" else None,
            "timestamp": ts,
            "inspector": inspector_info,
            "product": extracted["product"],
            "overall": compliance["overall"],
            "declarations": extracted["declarations"],
            "complianceChecks": compliance["checks"],
            "potentialViolations": compliance["violations"],
            "regions": regions,
            "review": review_obj
        }

    def get_inspection(self, inspection_id: str) -> Optional[dict]:
        return get_inspection(inspection_id)

    def get_status(self, inspection_id: str) -> Optional[dict]:
        return get_status(inspection_id)

    def get_all_inspections(
        self,
        search: Optional[str] = None,
        status: Optional[str] = None,
        category: Optional[str] = None,
        date: Optional[str] = None,
        page: int = 1,
        page_size: int = 10,
        customer_id: Optional[str] = None
    ) -> dict:
        ids = get_all_inspection_ids()
        items = []

        for iid in ids:
            insp = get_inspection(iid)
            if not insp:
                continue
            if customer_id and insp.get("customerId") != customer_id:
                continue

            hist = self._to_history_item(insp)

            # Search filter (productName, manufacturer, inspectionId)
            if search:
                s = search.strip().lower()
                p_name = hist["productName"].lower()
                mfg = hist["manufacturer"].lower()
                i_id = hist["inspectionId"].lower()
                if s not in p_name and s not in mfg and s not in i_id:
                    continue

            # Status filter
            if status:
                st = status.strip().upper()
                if hist["status"].upper() != st:
                    continue

            # Category filter
            if category:
                cat = category.strip().lower()
                h_cat = hist["category"].lower()
                h_cat_grp = hist["categoryGroup"].lower()
                if cat not in h_cat and cat not in h_cat_grp:
                    continue

            # Date filter (matches YYYY-MM-DD or YYYY-MM)
            if date:
                d = date.strip()
                if not hist["rawDate"].startswith(d) and not hist["date"].startswith(d):
                    continue

            items.append((insp.get("timestamp", 0), hist))

        # Sort descending by timestamp/date (Rule 13)
        items.sort(key=lambda x: x[0], reverse=True)
        sorted_history = [item[1] for item in items]

        total = len(sorted_history)
        start = (page - 1) * page_size
        end = start + page_size

        return {
            "items": sorted_history[start:end],
            "total": total,
            "page": page,
            "pageSize": page_size
        }

    def _to_history_item(self, insp: dict) -> dict:
        prod = insp.get("product", {})
        overall = insp.get("overall", {})
        inspector = insp.get("inspector", {})
        raw_date = insp.get("date", "")
        formatted_date = raw_date[:10] if len(raw_date) >= 10 else raw_date

        return {
            "inspectionId": insp.get("inspectionId", ""),
            "productName": prod.get("name") or "Packaged Commodity",
            "category": prod.get("category") or "General Goods",
            "categoryGroup": prod.get("subCategory") or "Packaged Commodity",
            "manufacturer": prod.get("manufacturer") or "Not Specified",
            "netQuantity": prod.get("netQuantity") or "N/A",
            "mrp": prod.get("mrp") or "N/A",
            "date": formatted_date,
            "rawDate": raw_date,
            "officer": inspector.get("name", "Officer Rajesh Kumar"),
            "complianceScore": overall.get("score", 0),
            "status": overall.get("status", "NEEDS REVIEW"),
            "hasReport": True,
            "hasEvidence": len(insp.get("regions", [])) > 0
        }

    def get_evidence(self, inspection_id: str) -> Optional[dict]:
        """Returns evidence structure conforming exactly to frontend contract (Rule 12)."""
        insp = get_inspection(inspection_id)
        if not insp:
            return None

        image_url = f"/api/inspections/{inspection_id}/image"
        findings = []

        for region in insp.get("regions", []):
            findings.append({
                "id": region["id"],
                "label": region["label"],
                "description": f"Detected {region['field']}: {region['extractedText']}",
                "bounds": {
                    "x": region["left"],
                    "y": region["top"],
                    "width": region["width"],
                    "height": region["height"]
                }
            })

        return {
            "id": inspection_id,
            "imageUrl": image_url,
            "findings": findings
        }
