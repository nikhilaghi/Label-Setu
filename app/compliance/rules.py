import re
from typing import Dict, Any, List, Optional

class ComplianceRule:
    def __init__(self, id: str, name: str):
        self.id = id
        self.name = name

    def evaluate(self, extracted: Dict[str, Any], regions: List[Dict[str, Any]]) -> Dict[str, Any]:
        raise NotImplementedError

    def _find_region_id(self, decl_ids: List[str], regions: List[Dict[str, Any]]) -> Optional[str]:
        for reg in regions:
            if reg.get("label") in decl_ids or any(reg.get("id") == f"reg_{did}" for did in decl_ids):
                return reg.get("id")
        return None

class ManufacturingDetailsRule(ComplianceRule):
    def __init__(self):
        super().__init__("chk_mfg", "Manufacturer/Packer Details")

    def evaluate(self, extracted: Dict[str, Any], regions: List[Dict[str, Any]]) -> Dict[str, Any]:
        product = extracted.get("product", {})
        mfg = product.get("manufacturer")
        packer = product.get("packer")
        importer = product.get("importer")
        region_id = self._find_region_id(["mfg", "packer", "importer"], regions)

        # Manufacturer is the primary declaration. Packer/importer are optional
        # for products where they do not apply, so their absence must not make a
        # correctly declared manufacturer fail this check.
        if mfg and len(mfg.strip()) >= 3:
            return {
                "id": self.id, "name": self.name, "status": "COMPLIANT",
                "confidence": 0.93,
                "explanation": f"Manufacturer/entity details declared: {mfg}.",
                "regionId": region_id
            }

        full_text = extracted.get("full_text", "").lower()
        if any(k in full_text for k in ["manufactured by", "mfd by", "mfg by", "marketed by", "packed by", "imported by"]):
            return {
                "id": self.id, "name": self.name, "status": "NEEDS REVIEW",
                "confidence": 0.65,
                "explanation": "A manufacturer/packer/importer label was detected, but a reliable entity name could not be extracted.",
                "regionId": region_id
            }

        return {
            "id": self.id, "name": self.name, "status": "NON-COMPLIANT",
            "confidence": 0.92,
            "explanation": "Mandatory manufacturer/entity name and address declaration is missing.",
            "regionId": None
        }


class NetQuantityRule(ComplianceRule):
    def __init__(self):
        super().__init__("chk_qty", "Net Quantity")

    def evaluate(self, extracted: Dict[str, Any], regions: List[Dict[str, Any]]) -> Dict[str, Any]:
        product = extracted.get("product", {})
        net_qty = product.get("netQuantity")
        region_id = self._find_region_id(["net_qty"], regions)

        if net_qty and re.fullmatch(r"\d+(?:\.\d+)?\s*(?:mg|g|kg|ml|l|pcs|units|n)", net_qty, re.I):
            return {
                "id": self.id, "name": self.name, "status": "COMPLIANT",
                "confidence": 0.94,
                "explanation": f"Net quantity correctly declared ({net_qty}) in a recognised unit.",
                "regionId": region_id
            }

        full_text = extracted.get("full_text", "").lower()
        if re.search(r"\bnet\s*(?:wt|weight|quantity|qty|content)\b", full_text):
            return {
                "id": self.id, "name": self.name, "status": "NEEDS REVIEW",
                "confidence": 0.60,
                "explanation": "A net-quantity declaration is visible, but its numeric value could not be reliably extracted.",
                "regionId": region_id
            }

        return {
            "id": self.id, "name": self.name, "status": "NON-COMPLIANT",
            "confidence": 0.95,
            "explanation": "Mandatory Net Quantity declaration is missing under the configured Legal Metrology rules.",
            "regionId": None
        }


class MRPRule(ComplianceRule):
    def __init__(self):
        super().__init__("chk_mrp", "MRP Declaration")

    def evaluate(self, extracted: Dict[str, Any], regions: List[Dict[str, Any]]) -> Dict[str, Any]:
        product = extracted.get("product", {})
        mrp = product.get("mrp")
        full_text = extracted.get("full_text", "")
        region_id = self._find_region_id(["mrp"], regions)

        tax_patterns = [
            r"incl(?:usive)?\s*(?:of)?\s*all\s*taxes",
            r"incl\.?\s*of\s*all\s*taxes",
            r"all\s*taxes\s*incl(?:uded)?",
            r"inclusive\s*taxes",
        ]
        has_tax_phrase = any(re.search(p, full_text, re.I) for p in tax_patterns)

        if mrp:
            return {
                "id": self.id, "name": self.name,
                "status": "COMPLIANT" if has_tax_phrase else "NEEDS REVIEW",
                "confidence": 0.94 if has_tax_phrase else 0.75,
                "explanation": (
                    f"MRP declared ({mrp}) with an inclusive-of-all-taxes statement."
                    if has_tax_phrase else
                    f"MRP declared ({mrp}), but the inclusive-of-all-taxes statement requires visual verification."
                ),
                "regionId": region_id
            }

        # Crucial distinction: the MRP label itself being present without a numeric
        # value is stronger evidence of a blank/invalid declaration than a random
        # price elsewhere on the package. Do not borrow numbers from other fields.
        if re.search(r"\b(?:mrp|m\.?r\.?p\.?|maximum\s+retail\s+price)\b", full_text, re.I):
            return {
                "id": self.id, "name": self.name, "status": "NON-COMPLIANT",
                "confidence": 0.92,
                "explanation": "MRP label detected, but no valid MRP amount is declared next to it.",
                "regionId": region_id
            }

        return {
            "id": self.id, "name": self.name, "status": "NON-COMPLIANT",
            "confidence": 0.95,
            "explanation": "Mandatory Maximum Retail Price (MRP) declaration is missing.",
            "regionId": region_id
        }


class DateInformationRule(ComplianceRule):
    def __init__(self):
        super().__init__("chk_date", "Date Information")

    def evaluate(self, extracted: Dict[str, Any], regions: List[Dict[str, Any]]) -> Dict[str, Any]:
        product = extracted.get("product", {})
        packed_date = product.get("packedDate")
        expiry_date = product.get("expiryDate")
        region_id = self._find_region_id(["date_info"], regions)

        if packed_date or expiry_date:
            dates_desc = []
            if packed_date:
                dates_desc.append(f"Packed: {packed_date}")
            if expiry_date:
                dates_desc.append(f"Expiry/Best Before: {expiry_date}")
            return {
                "id": self.id, "name": self.name, "status": "COMPLIANT",
                "confidence": 0.92,
                "explanation": f"Valid statutory date information extracted ({', '.join(dates_desc)}).",
                "regionId": region_id
            }

        full_text = extracted.get("full_text", "")
        if re.search(r"\b(?:pkd|packed|packaging|mfg|manufactured|expiry|exp|best before|use by)\b", full_text, re.I):
            return {
                "id": self.id, "name": self.name, "status": "NON-COMPLIANT",
                "confidence": 0.88,
                "explanation": "Date field label detected, but no valid packing/manufacturing or best-before/expiry date was extracted.",
                "regionId": region_id
            }

        return {
            "id": self.id, "name": self.name, "status": "NON-COMPLIANT",
            "confidence": 0.90,
            "explanation": "Mandatory Date of Packaging/Manufacturing or Best Before date is missing.",
            "regionId": None
        }


class ConsumerCareRule(ComplianceRule):
    def __init__(self):
        super().__init__("chk_care", "Consumer Care Details")

    def evaluate(self, extracted: Dict[str, Any], regions: List[Dict[str, Any]]) -> Dict[str, Any]:
        product = extracted.get("product", {})
        care = product.get("consumerCare")
        region_id = self._find_region_id(["consumer_care"], regions)

        if care and len(care.strip()) > 3:
            return {
                "id": self.id,
                "name": self.name,
                "status": "COMPLIANT",
                "confidence": 0.90,
                "explanation": f"Consumer care contact information provided ({care}).",
                "regionId": region_id
            }

        full_text = extracted.get("full_text", "").lower()
        if any(k in full_text for k in ["care", "customer", "helpline", "toll free", "feedback", "email", "@", "call", "complaint"]):
            return {
                "id": self.id,
                "name": self.name,
                "status": "NEEDS REVIEW",
                "confidence": 0.65,
                "explanation": "Consumer grievance cues found; verify phone/email clarity manually.",
                "regionId": region_id
            }

        return {
            "id": self.id,
            "name": self.name,
            "status": "NON-COMPLIANT",
            "confidence": 0.92,
            "explanation": "Mandatory consumer grievance / customer care contact details are missing.",
            "regionId": None
        }

class FontSizeRule(ComplianceRule):
    def __init__(self):
        super().__init__("chk_font", "Font Size / Readability")

    def evaluate(self, extracted: Dict[str, Any], regions: List[Dict[str, Any]]) -> Dict[str, Any]:
        # Evaluate OCR confidence across detected regions
        if not regions:
            return {
                "id": self.id,
                "name": self.name,
                "status": "NEEDS REVIEW",
                "confidence": 0.60,
                "explanation": "Limited text regions isolated for font readability assessment.",
                "regionId": None
            }

        confidences = [r.get("confidence", 0.0) for r in regions]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
        low_conf_count = sum(1 for c in confidences if c < 0.60)

        # As required: Low OCR confidence becomes NEEDS REVIEW, NEVER NON-COMPLIANT
        if avg_conf >= 0.70 and low_conf_count <= 1:
            return {
                "id": self.id,
                "name": self.name,
                "status": "COMPLIANT",
                "confidence": round(avg_conf, 2),
                "explanation": f"Text declarations demonstrate clear legibility (average OCR confidence {avg_conf * 100:.1f}%).",
                "regionId": regions[0].get("id") if regions else None
            }

        return {
            "id": self.id,
            "name": self.name,
            "status": "NEEDS REVIEW",
            "confidence": round(avg_conf, 2) if avg_conf > 0 else 0.60,
            "explanation": f"Some label declarations show optical ambiguity ({low_conf_count} regions with low confidence); officer review advised.",
            "regionId": regions[0].get("id") if regions else None
        }
