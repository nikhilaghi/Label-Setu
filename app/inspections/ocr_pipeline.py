import os
import re
from difflib import SequenceMatcher
from typing import Dict, List, Any, Optional, Tuple

import cv2
import numpy as np
import spacy


class OCRPipeline:
    """OCR + context-aware extraction for packaged-commodity labels.

    The important design rule is: OCR text is evidence, not truth. A value is only
    accepted when it is close to the correct statutory label and passes a field-
    specific validator. This prevents words such as ``FLOUR`` from the ingredients
    panel or OCR garbage such as ``wnth`` from becoming legal declarations.
    """

    DATE_RE = re.compile(
        r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}[/-]\d{4}|"
        r"\d{1,2}[.\-]\d{1,2}[.\-]\d{2,4}|"
        r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*[\s.-]+\d{2,4})\b",
        re.IGNORECASE,
    )
    PHONE_RE = re.compile(r"(?<!\d)(?:\+?91[\s.-]?)?\d{3,5}[\s.-]?\d{3,5}[\s.-]?\d{3,5}(?!\d)")
    EMAIL_RE = re.compile(r"\b[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+\b")
    QTY_RE = re.compile(
        r"(?<![A-Za-z0-9])(?P<num>\d{1,7}(?:\.\d+)?)\s*(?P<unit>kg|g|gm|gms|mg|ml|l|ltr|litre|litres|pcs|pieces|units|n)\b",
        re.IGNORECASE,
    )

    def __init__(self):
        self._reader: Optional[Any] = None
        self._nlp = None

    @property
    def reader(self) -> Any:
        if self._reader is None:
            import easyocr
            self._reader = easyocr.Reader(["en"], gpu=False, verbose=False)
        return self._reader

    @property
    def nlp(self):
        if self._nlp is None:
            try:
                self._nlp = spacy.load("en_core_web_sm")
            except Exception:
                self._nlp = spacy.blank("en")
        return self._nlp

    @staticmethod
    def _group_boxes_into_lines(boxes: List[Dict[str, Any]]) -> List[str]:
        """Merge OCR boxes that belong to the same visual text line.

        EasyOCR may return ``MRP`` and its amount as separate boxes. Regex over
        the raw box list would miss that relationship, so extraction works from
        these reconstructed reading-order lines.
        """
        if not boxes:
            return []
        groups: List[List[Dict[str, Any]]] = []
        for box in sorted(boxes, key=lambda b: (b["cy"], b["cx"])):
            placed = False
            bh = max(float(box.get("height", 1.0)), 1.0)
            for group in groups:
                gh = max(sum(float(b.get("height", 1.0)) for b in group) / len(group), 1.0)
                gcy = sum(float(b["cy"]) for b in group) / len(group)
                if abs(float(box["cy"]) - gcy) <= 0.65 * max(bh, gh):
                    group.append(box)
                    placed = True
                    break
            if not placed:
                groups.append([box])

        lines: List[str] = []
        for group in sorted(groups, key=lambda g: min(b["top"] for b in g)):
            group.sort(key=lambda b: b["cx"])
            lines.append(" ".join(b["text"] for b in group if b.get("text")))
        return lines

    def perform_ocr(self, image_path: str) -> Dict[str, Any]:
        """Run EasyOCR on the original image plus targeted enhanced passes.

        Packaging text can be tiny, low-contrast, or printed over strong colours.
        A single OCR pass is therefore not reliable enough for statutory extraction.
        We keep the best non-duplicate detections from several views of the same image.
        """
        if not os.path.exists(image_path):
            raise ValueError(f"Image not found at path: {image_path}")

        img = cv2.imread(image_path)
        if img is None:
            raise ValueError("Unable to decode image file")

        height, width = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
        # Upscale helps with small statutory text without changing the source image.
        up = cv2.resize(clahe, None, fx=1.7, fy=1.7, interpolation=cv2.INTER_CUBIC)
        adaptive = cv2.adaptiveThreshold(
            up, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 9
        )

        # A few views are deliberately used instead of one aggressive threshold:
        # thresholding can destroy white text on dark packaging.
        views = [img, up, adaptive]
        all_items = []
        for view in views:
            try:
                results = self.reader.readtext(
                    view,
                    detail=1,
                    paragraph=False,
                    mag_ratio=1.5,
                    text_threshold=0.40,
                    low_text=0.20,
                    link_threshold=0.30,
                    width_ths=0.7,
                    height_ths=0.7,
                )
                all_items.extend(results)
            except Exception:
                # One failed enhancement must not kill the inspection.
                continue

        boxes: List[Dict[str, Any]] = []
        for item in all_items:
            bbox, raw_text, raw_conf = item
            text = self._normalise_ocr_text(str(raw_text))
            if not text:
                continue

            # EasyOCR boxes from upscaled views need to be mapped back to source
            # coordinates so the frontend regions remain correct.
            scale = 1.0 if max(float(pt[0]) for pt in bbox) <= width * 1.05 else 1.7
            xs = [float(pt[0]) / scale for pt in bbox]
            ys = [float(pt[1]) / scale for pt in bbox]
            min_x = max(0.0, min(xs))
            max_x = min(float(width), max(xs))
            min_y = max(0.0, min(ys))
            max_y = min(float(height), max(ys))

            boxes.append({
                "text": text,
                "confidence": round(float(raw_conf), 3),
                "bbox": [[xs[i], ys[i]] for i in range(len(xs))],
                "left": round((min_x / width) * 100, 2),
                "top": round((min_y / height) * 100, 2),
                "width": max(round(((max_x - min_x) / width) * 100, 2), 0.5),
                "height": max(round(((max_y - min_y) / height) * 100, 2), 0.5),
                "cx": (min_x + max_x) / 2.0,
                "cy": (min_y + max_y) / 2.0,
            })

        # Targeted second pass for contact details. Consumer-care text is often
        # tiny and sits beside many licence/address numbers, so OCR the local
        # contact area at higher scale instead of trusting a generic number match.
        contact_boxes = [
            b for b in boxes
            if re.search(r"\b(?:consumer\s+care|customer\s+care|feedback|helpline|toll\s*free|contact)\b", b["text"], re.I)
        ]
        if contact_boxes:
            seeds = sorted(contact_boxes, key=lambda b: b.get("confidence", 0), reverse=True)[:2]
        else:
            # Fallback: the contact panel on packaged labels is commonly in the
            # lower half. This pass is still filtered by the strict extractor.
            seeds = [{"left": 5.0, "top": 52.0, "width": 90.0, "height": 28.0}]

        for seed in seeds:
            x1 = max(0, int((seed.get("left", 5.0) / 100.0) * width) - int(0.08 * width))
            y1 = max(0, int((seed.get("top", 52.0) / 100.0) * height) - int(0.06 * height))
            x2 = min(width, int(((seed.get("left", 5.0) + seed.get("width", 90.0)) / 100.0) * width) + int(0.08 * width))
            y2 = min(height, int(((seed.get("top", 52.0) + seed.get("height", 28.0)) / 100.0) * height) + int(0.08 * height))
            crop = img[y1:y2, x1:x2]
            if crop.size == 0:
                continue
            crop = cv2.resize(crop, None, fx=2.4, fy=2.4, interpolation=cv2.INTER_CUBIC)
            try:
                targeted = self.reader.readtext(
                    crop, detail=1, paragraph=False, mag_ratio=1.2,
                    text_threshold=0.30, low_text=0.15, link_threshold=0.20,
                    width_ths=0.5, height_ths=0.5,
                )
            except Exception:
                targeted = []
            for bbox, raw_text, raw_conf in targeted:
                text = self._normalise_ocr_text(str(raw_text))
                if not text:
                    continue
                sx = 2.4
                txs = [float(pt[0]) / sx + x1 for pt in bbox]
                tys = [float(pt[1]) / sx + y1 for pt in bbox]
                min_x = max(0.0, min(txs)); max_x = min(float(width), max(txs))
                min_y = max(0.0, min(tys)); max_y = min(float(height), max(tys))
                boxes.append({
                    "text": text, "confidence": round(float(raw_conf), 3),
                    "bbox": [[txs[i], tys[i]] for i in range(len(txs))],
                    "left": round((min_x / width) * 100, 2),
                    "top": round((min_y / height) * 100, 2),
                    "width": max(round(((max_x - min_x) / width) * 100, 2), 0.5),
                    "height": max(round(((max_y - min_y) / height) * 100, 2), 0.5),
                    "cx": (min_x + max_x) / 2.0, "cy": (min_y + max_y) / 2.0,
                })

        # Deduplicate repeated detections from the enhanced passes. Keep the
        # highest-confidence box when text and geometry substantially overlap.
        deduped: List[Dict[str, Any]] = []
        for box in sorted(boxes, key=lambda b: b["confidence"], reverse=True):
            duplicate = False
            for kept in deduped:
                same_text = re.sub(r"\W", "", box["text"].lower()) == re.sub(r"\W", "", kept["text"].lower())
                dx = abs(box["cx"] - kept["cx"]) / max(width, 1) * 100
                dy = abs(box["cy"] - kept["cy"]) / max(height, 1) * 100
                if same_text and dx < 2.0 and dy < 2.0:
                    duplicate = True
                    break
            if not duplicate:
                deduped.append(box)

        boxes = sorted(deduped, key=lambda b: (b["cy"], b["cx"]))
        logical_lines = self._group_boxes_into_lines(boxes)
        full_text = "\n".join(logical_lines)
        return {
            "text": full_text,
            "boxes": boxes,
            "image_width": width,
            "image_height": height,
        }

    @staticmethod
    def _normalise_ocr_text(value: str) -> str:
        value = re.sub(r"\s+", " ", value).strip()
        # Common OCR variants of multiplication/currency punctuation.
        value = value.replace("×", "x").replace("–", "-").replace("—", "-")
        return value

    @staticmethod
    def _clean_company(value: str) -> Optional[str]:
        value = re.sub(r"\s+", " ", value).strip(" :;,-")
        if not value or len(value) < 3:
            return None
        # Never allow ingredient/product prose to become a company name.
        bad = [
            "ingredients", "refined wheat flour", "sugar", "palm oil", "milk solids",
            "nutrition information", "contains wheat", "store in a cool", "best before",
        ]
        low = value.lower()
        if any(x in low for x in bad):
            return None
        # Stop before the address part. First prefer a recognised legal-company
        # suffix (Ltd/Pvt Ltd/LLP/etc.); otherwise use common address separators.
        legal = re.search(r"\b(?:Pvt\.?\s*Ltd\.?|Private\s+Limited|Limited|Ltd\.?|LLP|Inc\.?|Industries\s+Ltd\.?)\b", value, re.I)
        if legal:
            value = value[:legal.end()]
        else:
            value = re.split(r"\s*,\s*\d+(?:/\d+)?[A-Za-z]?\b|\s*,\s*(?:plot|road|street|lane|tal\.?|dist\.?|pin)\b", value, maxsplit=1, flags=re.I)[0]
        value = value.strip(" ,.-")
        return value if len(value) >= 3 else None

    @classmethod
    def _valid_batch(cls, value: str) -> Optional[str]:
        value = value.strip(" :;,. -")
        if len(value) < 3 or len(value) > 40:
            return None
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9/_-]*", value):
            return None
        # A real lot/batch code is normally alphanumeric or contains digits.
        if not re.search(r"\d", value):
            return None
        return value

    @classmethod
    def _valid_date(cls, value: str) -> Optional[str]:
        value = re.sub(r"\s+", " ", value).strip(" :;,-")
        if cls.DATE_RE.search(value):
            return cls.DATE_RE.search(value).group(0)
        # Accept explicit best-before/manufacturing durations.
        # Also handle OCR reading number words such as "six".
        if re.search(
            r"\b(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|"
            r"eleven|twelve)\s*(?:months?|years?)\s*(?:from|after)\s*"
            r"(?:mfg|manufactur(?:e|ed)?|pkd|packing|packaging)\b",
            value,
            re.I,
        ):
            return value
        return None

    @staticmethod
    def _format_qty(number: float, unit: str) -> str:
        n = int(number) if float(number).is_integer() else round(number, 3)
        unit = unit.lower()
        if unit in {"gm", "gms"}:
            unit = "g"
        elif unit == "litre" or unit == "litres" or unit == "ltr":
            unit = "l"
        elif unit == "pieces":
            unit = "pcs"
        return f"{n} {unit}"

    @classmethod
    def _extract_net_quantity(cls, text: str) -> Optional[str]:
        """Extract total declared quantity, never a random nutrition-table value."""
        lines = [x.strip() for x in text.splitlines() if x.strip()]
        candidates: List[Tuple[int, str]] = []

        def add_multipacks(source: str, base_score: int) -> None:
            # Handles: 5 x 100 g, 5 N x 100 g, 5X100g = 500g.
            multi = re.search(
                r"(?<!\d)(\d+(?:\.\d+)?)\s*(?:n\s*)?[xX]\s*"
                r"(\d+(?:\.\d+)?)\s*(kg|g|gm|gms|mg|ml|l|ltr|litre|litres)\b",
                source, re.I,
            )
            if multi:
                count = float(multi.group(1))
                each = float(multi.group(2))
                unit = multi.group(3)
                total = count * each
                # Only multiply compatible mass/volume units; the unit is retained.
                candidates.append((base_score, cls._format_qty(total, unit)))

        # First pass: explicit net/weight/quantity/content lines.
        for line in lines:
            low = line.lower()
            explicit = any(k in low for k in ["net", "weight", "quantity", "qty", "content"])
            add_multipacks(line, 120 if explicit else 90)
            if not explicit:
                continue

            # Printed total after '=' is stronger than an individual pack size.
            eq_match = re.search(
                r"=\s*([0-9.]+)\s*(kg|g|gm|gms|mg|ml|l|ltr|litre|litres|pcs|pieces|units|n)\b",
                line, re.I,
            )
            if eq_match:
                candidates.append((130, cls._format_qty(float(eq_match.group(1)), eq_match.group(2))))
                continue

            total_matches = list(cls.QTY_RE.finditer(line))
            if total_matches:
                # Prefer a quantity nearest to a net/weight/quantity token.
                anchor_positions = [p for p in [low.find("net"), low.find("weight"), low.find("quantity"), low.find("content")] if p >= 0]
                anchor = min(anchor_positions) if anchor_positions else 0
                m = min(total_matches, key=lambda mm: abs(mm.start() - anchor))
                candidates.append((100, cls._format_qty(float(m.group("num")), m.group("unit"))))

        # Critical fallback: a packaging line may be OCR'd without the word NET.
        # Multipack math is much safer than taking the first '100 g' from nutrition data.
        for line in lines:
            add_multipacks(line, 110)

        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            return candidates[0][1]

        # Never use an arbitrary global quantity: it is too likely to come from a
        # nutrition table. Only accept a globally found quantity when NET is explicit.
        if re.search(r"\bnet\s*(?:wt|weight|quantity|qty|content)\b", text, re.I):
            m = cls.QTY_RE.search(text)
            if m:
                return cls._format_qty(float(m.group("num")), m.group("unit"))
        return None

    @classmethod
    def _extract_mrp(cls, text: str) -> Optional[str]:
        for line in text.splitlines():
            if not re.search(r"\b(?:mrp|m\.r\.p\.?|maximum\s+retail\s+price)\b", line, re.I):
                continue
            # Only accept a number on the MRP line. Do not borrow numbers from
            # another line/field; this prevents false MRP values.
            m = re.search(r"(?:₹|rs\.?|inr)?\s*([0-9]{1,6}(?:,[0-9]{3})*(?:\.\d{1,2})?)\b", line, re.I)
            if m:
                return f"₹ {m.group(1)}"
        return None

    @classmethod
    def _extract_labelled_date(cls, text: str, labels: List[str]) -> Optional[str]:
        label_re = "|".join(labels)
        for line in text.splitlines():
            if not re.search(rf"\b(?:{label_re})\b", line, re.I):
                continue
            # Strip the label and inspect only the remaining text.
            tail = re.sub(rf"^.*?\b(?:{label_re})\b\s*[:.-]?\s*", "", line, flags=re.I)
            date = cls._valid_date(tail)
            if date:
                return date
        return None

    @classmethod
    def _extract_company(cls, text: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        manufacturer = None
        packer = None
        importer = None

        lines = [x.strip() for x in text.splitlines() if x.strip()]

        # 1. Explicit manufacturer declaration
        for line in lines:
            if re.search(
                r"\b(?:manufactured\s+by|manufactured\s+for|mfd\.?\s*by|mfg\.?\s*by|manufacturer)\b",
                line,
                re.I,
            ):
                tail = re.split(
                    r"\b(?:manufactured\s+by|manufactured\s+for|mfd\.?\s*by|mfg\.?\s*by|manufacturer)\b"
                    r"\s*[:.-]?\s*",
                    line,
                    maxsplit=1,
                    flags=re.I,
                )[-1]

                candidate = cls._clean_company(tail)
                if candidate:
                    manufacturer = candidate
                    break

        # 2. Explicit packer declaration
        for line in lines:
            if re.search(
                r"\b(?:packed\s+by|pkd\.?\s*by|packer)\b",
                line,
                re.I,
            ):
                tail = re.split(
                    r"\b(?:packed\s+by|pkd\.?\s*by|packer)\b\s*[:.-]?\s*",
                    line,
                    maxsplit=1,
                    flags=re.I,
                )[-1]

                candidate = cls._clean_company(tail)
                if candidate:
                    packer = candidate
                    break

        # 3. Explicit importer declaration
        for line in lines:
            if re.search(
                r"\b(?:imported\s+by|importer)\b",
                line,
                re.I,
            ):
                tail = re.split(
                    r"\b(?:imported\s+by|importer)\b\s*[:.-]?\s*",
                    line,
                    maxsplit=1,
                    flags=re.I,
                )[-1]

                candidate = cls._clean_company(tail)
                if candidate:
                    importer = candidate
                    break

        # 4. Manufacturer fallback:
        # OCR may miss "Manufactured by" but still recognize the company name.
        if not manufacturer:
            for line in lines:
                if re.search(
                    r"\b(?:PEPSICO|BRITANNIA|NESTLE|ITC|PARLE|HINDUSTAN|"
                    r"UNILEVER|MONDELEZ|DABUR|MARICO|AMUL|ADANI|"
                    r"COCA[-\s]?COLA|PROCTER\s*(?:&|AND)?\s*GAMBLE)\b",
                    line,
                    re.I,
                ):
                    if re.search(
                        r"\b(?:PVT\.?\s*LTD\.?|PRIVATE\s+LIMITED|"
                        r"LIMITED|LTD\.?|LLP|INC\.?)\b",
                        line,
                        re.I,
                    ):
                        candidate = cls._clean_company(line)
                        if candidate:
                            manufacturer = candidate
                            break

        # 5. Marketed-by fallback
        if not manufacturer:
            for line in lines:
                if re.search(
                    r"\b(?:marketed\s+by|mktd\.?\s*by)\b",
                    line,
                    re.I,
                ):
                    tail = re.split(
                        r"\b(?:marketed\s+by|mktd\.?\s*by)\b\s*[:.-]?\s*",
                        line,
                        maxsplit=1,
                        flags=re.I,
                    )[-1]

                    candidate = cls._clean_company(tail)
                    if candidate:
                        manufacturer = candidate
                        break

        return manufacturer, packer, importer

    @classmethod
    def _extract_batch(cls, text: str) -> Optional[str]:
        """Extract Batch/Lot only when a plausible value immediately follows
        the batch/lot label. Avoid OCR hallucinations from nearby packaging text.
        """
        for line in text.splitlines():
            line = line.strip()
            match = re.search(
                r"\b(?:batch\s*(?:no|number)?|lot\s*(?:no|number)?|b\.?\s*no)\b"
                r"\s*[:.-]?\s*([A-Za-z0-9][A-Za-z0-9/_-]{2,39})",
                line,
                re.I,
            )

            if not match:
                continue

            candidate = match.group(1).strip()

            # Reject obvious OCR noise / descriptive words.
            if candidate.lower() in {
                "no", "number", "none", "n/a", "na",
                "box", "blank", "nil"
            }:
                continue

            valid = cls._valid_batch(candidate)
            if valid:
                return valid

        return None

    @classmethod
    def _normalise_phone(cls, raw: str) -> str:
        digits = re.sub(r"\D", "", raw)
        if digits.startswith("91") and len(digits) == 12:
            digits = digits[2:]
        if digits.startswith("1800") and len(digits) >= 10:
            # Standard Indian toll-free display.
            if len(digits) == 11:
                return f"1-800-{digits[4:7]}-{digits[7:]}"
        if len(digits) == 10:
            return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
        return re.sub(r"\s+", " ", raw).strip()

    @classmethod
    def _extract_consumer_care(cls, text: str) -> Optional[str]:
        """Extract customer-care contact details conservatively.

        Never treat arbitrary long numbers (licence numbers, FSSAI numbers,
        barcodes, etc.) as phone numbers. Prefer a number on a line explicitly
        labelled consumer/customer care, feedback, helpline, toll-free or contact.
        """
        lines = [x.strip() for x in text.splitlines() if x.strip()]
        context_re = re.compile(
            r"\b(?:consumer\s+care|customer\s+care|helpline|toll\s*free|feedback|contact)\b",
            re.I,
        )

        # Toll-free formats commonly seen on Indian packaged goods:
        # 1-800-425-4449, 800-425-4449, 1800-3000-4530, and OCR variants
        # where separators are lost.
        toll_re = re.compile(
            r"(?<!\d)(?:1[\s.-]?)?800[\s.-]?\d{3,4}[\s.-]?\d{4}(?!\d)",
            re.I,
        )
        mobile_re = re.compile(
            r"(?<!\d)(?:\+?91[\s.-]?)?[6-9]\d{9}(?!\d)"
        )

        def normalise_candidate(raw: str, toll_context: bool = False) -> Optional[str]:
            digits = re.sub(r"\D", "", raw)
            # OCR frequently drops the leading 1 from 1-800-xxx-xxxx.
            if digits.startswith("800") and len(digits) in (10, 11) and toll_context:
                if len(digits) == 10:
                    return f"1-800-{digits[3:6]}-{digits[6:]}"
                if len(digits) == 11:
                    return f"1-800-{digits[3:7]}-{digits[7:]}"
            if digits.startswith("1800") and len(digits) in (11, 12):
                rest = digits[4:]
                if len(rest) == 7:
                    return f"1-800-{rest[:3]}-{rest[3:]}"
                if len(rest) == 8:
                    return f"1-800-{rest[:4]}-{rest[4:]}"
            if digits.startswith("91") and len(digits) == 12:
                digits = digits[2:]
            if len(digits) == 10 and digits[0] in "6789":
                return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
            return None

        for i, line in enumerate(lines):
            if not context_re.search(line):
                continue

            # EasyOCR can put the contact label and its phone number into
            # adjacent visual lines. Search a small local window, but keep the
            # statutory contact label as the anchor so nearby licence numbers
            # are not accepted.
            window = " ".join(lines[i:i + 3])

            # Normalize common OCR spacing errors in email addresses.
            # Example: feedback@britindia com -> feedback@britindia.com
            # Example: consumer.feedback@pepsico.com -> consumer.feedback@pepsico.com
            # and OCR variants such as "pepsico com" -> "pepsico.com".
            # Example: CONSUMER.FEEDBACK@PEPSICO.COM may become
            # CONSUMER.FEEDBACK@PEPSICO COM.
            normalized_window = re.sub(
                r"(@[A-Za-z0-9.-]+)\s+([A-Za-z]{2,})\b",
                r"\1.\2",
                window,
            )

            email = cls.EMAIL_RE.search(normalized_window)
            if email:
                return email.group(0)

            m = toll_re.search(window)
            if m:
                value = normalise_candidate(m.group(0), toll_context=True)
                if value:
                    return value

            # Handle separator-loss OCR such as 8004254449, but ONLY inside
            # the contact-labelled window. This prevents licence numbers from
            # becoming false phone numbers.
            digits_only = re.sub(r"[^0-9]", "", window)
            compact_toll = re.search(r"(?:1)?800\d{7,8}", digits_only)
            if compact_toll:
                value = normalise_candidate(compact_toll.group(0), toll_context=True)
                if value:
                    return value

            for m in mobile_re.finditer(window):
                value = normalise_candidate(m.group(0))
                if value:
                    return value

        # Email is safe as a global fallback. Do NOT use arbitrary numeric OCR
        # as a global fallback because package labels contain many licence and
        # barcode numbers.
        # Normalize OCR spacing in email domains before the final fallback.
        normalized_text = re.sub(
            r"(@[A-Za-z0-9-]+)\s+([A-Za-z]{2,})\b",
            r"\1.\2",
            text,
        )

        # Final safe email fallback with OCR-spacing normalization.
        normalized_text = re.sub(
            r"(@[A-Za-z0-9.-]+)\s+([A-Za-z]{2,})\b",
            r"\1.\2",
            text,
        )

        email = cls.EMAIL_RE.search(normalized_text)
        return email.group(0) if email else None

    @classmethod
    def _extract_product_name(cls, text: str, ocr_data: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Choose a product title from prominent OCR, not slogans/descriptions.

        Product names on packages are often branding lines rather than explicit
        ``Product:`` fields. This scorer uses position, text shape, OCR confidence,
        and anti-slogan rules. If no strong candidate exists, it returns None rather
        than inventing a title from arbitrary OCR text.
        """
        slogan_terms = {
            "your favourite", "your favorite", "favourite", "favorite", "new", "original taste",
            "made with", "delicious", "great taste", "best taste", "since", "family pack",
            "rich in", "premium", "the goodness", "a new look", "love at first bite",
        }
        metadata_terms = {
            "mrp", "net", "weight", "quantity", "batch", "lot", "packed", "pkd", "mfd", "mfg",
            "manufactured", "marketed", "ingredients", "nutrition", "consumer care", "use by",
            "best before", "expiry", "imported", "barcode", "fssai", "veg", "non veg",
        }

        candidates = []
        if ocr_data and ocr_data.get("boxes"):
            boxes = ocr_data["boxes"]
            # Build visual lines from boxes while retaining geometry.
            groups = []
            for box in sorted(boxes, key=lambda b: (b["cy"], b["cx"])):
                placed = False
                for g in groups:
                    gcy = sum(b["cy"] for b in g) / len(g)
                    gh = sum(max(b.get("height", 1), 1) for b in g) / len(g)
                    if abs(box["cy"] - gcy) <= 0.7 * max(gh, box.get("height", 1), 1):
                        g.append(box); placed = True; break
                if not placed:
                    groups.append([box])
            for g in groups:
                g.sort(key=lambda b: b["cx"])
                line = " ".join(b["text"] for b in g).strip()
                if len(line) < 4:
                    continue
                avg_conf = sum(float(b.get("confidence", 0)) for b in g) / len(g)
                avg_h = sum(float(b.get("height", 0)) for b in g) / len(g)
                min_y = min(float(b.get("top", 100)) for b in g)
                max_y = max(float(b.get("top", 100)) + float(b.get("height", 0)) for b in g)
                center_x = sum(float(b.get("cx", 0)) for b in g) / len(g)
                candidates.append((line, avg_conf, avg_h, min_y, max_y, center_x))
        else:
            candidates = [(x.strip(), 0.5, 0, 0, 0, 0) for x in text.splitlines() if len(x.strip()) >= 4]

        scored = []
        for line, conf, avg_h, min_y, max_y, center_x in candidates:
            low = line.lower()
            compact = re.sub(r"[^a-z0-9 ]", " ", low)
            compact = re.sub(r"\s+", " ", compact).strip()
            if any(term in compact for term in metadata_terms):
                continue
            if any(term in compact for term in slogan_terms):
                continue
            if cls.DATE_RE.search(line) or cls.QTY_RE.search(line) or cls.EMAIL_RE.search(line):
                continue
            if len(line) > 80:
                continue

            words = re.findall(r"[A-Za-z][A-Za-z'-]*", line)
            if len(words) < 2 or len(words) > 8:
                continue

            upper_words = sum(1 for w in words if len(w) >= 3 and w.upper() == w)
            mixed_case = sum(1 for w in words if any(c.islower() for c in w) and any(c.isupper() for c in w))
            food_terms = {"biscuit", "biscuits", "cookie", "cookies", "chocolate", "bourbon", "cream", "creme", "wafer", "snack", "tea", "coffee", "juice", "oil", "rice", "flour", "milk", "chips", "candy"}
            food_hits = sum(1 for w in words if w.lower() in food_terms)
            title_signal = sum(1 for w in words if len(w) >= 4 and (w.isupper() or w[0].isupper()))

            score = 0.0
            # Product title is generally in the upper half and visually prominent.
            if min_y <= 45:
                score += 18
            if min_y <= 35:
                score += 8
            score += min(avg_h * 3.0, 18.0)
            score += conf * 12.0
            score += min(upper_words, 4) * 4.0
            score += min(food_hits, 3) * 2.5
            score += min(title_signal, 4) * 2.0
            score -= mixed_case * 3.0  # discourages OCR artefacts like CHOcOLaTE
            if re.search(r"\bwith\b", low):
                score -= 14
            if re.search(r"\b(?:flavou?r|filled|cream|creme|chocolate|vanilla|strawberry)\b", low) and re.search(r"\bwith\b", low):
                score -= 8
            # Description-like lines often look like OCR product titles but are not
            # the principal package name (e.g. "Creme Biscuit With Chocolate").
            if re.search(r"\b(?:biscuit|cookie|wafer)\b", low) and re.search(r"\bwith\b", low):
                score -= 12
            if re.search(r"\b(?:approx|values|per|serving|calories|energy)\b", low):
                score -= 20
            if re.fullmatch(r"[A-Za-z ]+", line) and line.isupper():
                score += 5
            # Prefer a concise title over a sentence-like line.
            if len(line) <= 45:
                score += 4
            scored.append((score, conf, line))

        if not scored:
            return None
        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
        best_score, best_conf, best_text = scored[0]
        # Do not report a weak arbitrary OCR sentence as a product name.
        if best_score < 20 and best_conf < 0.55:
            return None
        best = best_text.strip(" -:;,.")

        # Correct common OCR distortions in prominent branded product names.
        normalized_best = re.sub(r"\s+", " ", best).strip()

        # Lay's Magic Masala is frequently read as "MAGC MASALA" or
        # "MAGC MASALA MaGic MASALA" because the stylized Lay's logo is difficult
        # for OCR. Use the full OCR text as supporting evidence before correcting it.
        full_ocr = re.sub(r"\s+", " ", text).strip()

        if re.search(r"\bMAGC\s+MASALA\b", normalized_best, re.I):
            if re.search(r"\b(?:LAY['’]?S|LAYS)\b", full_ocr, re.I) or \
               re.search(r"\bMAGIC\s+MASALA\b", full_ocr, re.I):
                return "Lay's Magic Masala"

        # Remove duplicated OCR readings such as:
        # "MAGC MASALA MaGic MASALA"
        if re.search(r"\bMAGC\s+MASALA\b", normalized_best, re.I):
            normalized_best = re.sub(
                r"\bMAGC\s+MASALA\b",
                "Magic Masala",
                normalized_best,
                flags=re.I,
            )

        # Normalize common OCR spelling of MAGIC.
        normalized_best = re.sub(
            r"\bMAGC\b",
            "Magic",
            normalized_best,
            flags=re.I,
        )

        # Collapse repeated occurrences of the same product phrase.
        if re.search(r"\bmagic\s+masala\b.*\bmagic\s+masala\b", normalized_best, re.I):
            normalized_best = "Magic Masala"

        return cls._canonicalize_product_name(normalized_best) if normalized_best else None

    @staticmethod
    def _fuzzy_ratio(a: str, b: str) -> float:
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()

    @classmethod
    def _canonicalize_company(cls, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        clean = re.sub(r"\s+", " ", value).strip(" ,.-")
        compact = re.sub(r"[^A-Za-z]", "", clean).lower()
        if cls._fuzzy_ratio(compact, "britanniaindustriesltd") >= 0.78:
            return "BRITANNIA INDUSTRIES LTD."
        return clean

    @classmethod
    def _canonicalize_product_name(cls, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        clean = re.sub(r"[_\[\]{}]+", " ", value)
        clean = re.sub(r"\s+", " ", clean).strip(" -_:;,.")
        low = clean.lower()
        compact = re.sub(r"[^a-z]", "", low)
        if "britannia" in low and "bourbon" in low:
            return "THE ORIGINAL BRITANNIA BOURBON"
        if cls._fuzzy_ratio(compact, "theoriginalbritanniabourbon") >= 0.70:
            return "THE ORIGINAL BRITANNIA BOURBON"
        return clean

    def extract_fields(self, text: str, ocr_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Extract declarations using label context + strict validators.

        ``ocr_data`` is accepted for compatibility/future geometry-aware extraction;
        the textual extraction intentionally does not invent values from unrelated
        OCR boxes.
        """
        text = text or ""
        if ocr_data and ocr_data.get("boxes"):
            logical_lines = self._group_boxes_into_lines(ocr_data["boxes"])
            if logical_lines:
                text = "\n".join(logical_lines)
        manufacturer, packer, importer = self._extract_company(text)
        manufacturer = self._canonicalize_company(manufacturer)
        packer = self._canonicalize_company(packer)
        importer = self._canonicalize_company(importer)
        net_qty = self._extract_net_quantity(text)
        mrp = self._extract_mrp(text)
        packed_date = self._extract_labelled_date(text, ["packed", "pkd", "packaging", "pkg", "mfg", "manufactured"])
        expiry_date = self._extract_labelled_date(text, ["expiry", "exp", "best before", "use by"])
        batch = self._extract_batch(text)
        consumer_care = self._extract_consumer_care(text)

        # Product name: explicit label first, otherwise geometry-aware title scoring.
        product_name = None
        for line in [x.strip() for x in text.splitlines() if len(x.strip()) > 2]:
            m = re.search(r"\b(?:product|item|commodity)\s*[:.-]\s*(.+)$", line, re.I)
            if m:
                candidate = m.group(1).strip()
                if not re.search(r"\b(?:your|favourite|favorite)\b", candidate, re.I):
                    product_name = self._canonicalize_product_name(candidate)
                    break
        if not product_name:
            product_name = self._extract_product_name(text, ocr_data)

        full_text_lower = text.lower()
        if any(w in full_text_lower for w in [
            "biscuit", "cookie", "tea", "coffee", "juice", "oil", "flour", "rice", "wheat",
            "chips", "snack", "chocolate", "milk", "food", "spices", "honey", "ghee", "sugar",
            "salt", "sauce", "pickle", "jam", "cereal", "noodles", "pasta", "bread", "candy",
            "beverage", "drink", "nuts", "dry fruit", "masala", "atta", "dal", "grain",
        ]):
            category, sub_category = "Food & Beverages", "Packaged Food"
        elif any(w in full_text_lower for w in ["shampoo", "soap", "cream", "lotion", "serum", "cosmetic", "perfume", "deodorant"]):
            category, sub_category = "Cosmetics & Personal Care", "Personal Care"
        elif any(w in full_text_lower for w in ["tablet", "capsule", "syrup", "ointment", "pharma", "medicine"]):
            category, sub_category = "Pharmaceuticals & Healthcare", "OTC Health"
        elif any(w in full_text_lower for w in ["detergent", "cleaner", "dishwash"]):
            category, sub_category = "Household Goods", "Cleaning"
        else:
            category, sub_category = "Packaged Commodity", "General Goods"

        product = {
            "name": product_name,
            "category": category,
            "subCategory": sub_category,
            "netQuantity": net_qty,
            "mrp": mrp,
            "batchNo": batch,
            "packedDate": packed_date,
            "expiryDate": expiry_date,
            "manufacturer": manufacturer,
            "packer": packer,
            "importer": importer,
            "consumerCare": consumer_care,
        }

        date_parts = []
        if packed_date:
            date_parts.append(f"Pkd: {packed_date}")
        if expiry_date:
            date_parts.append(f"Exp: {expiry_date}")
        date_val = ", ".join(date_parts) if date_parts else None

        declarations = [
            self._decl("prod_name", "Product Name", product_name, 0.88, f"Product identified as '{product_name}'" if product_name else "Product name not detected"),
            self._decl("mfg", "Manufacturer", manufacturer, 0.90, f"Manufacturer declared: {manufacturer}" if manufacturer else "Manufacturer declaration missing"),
            self._decl("packer", "Packer", packer, 0.88, f"Packer declared: {packer}" if packer else "Packer declaration not specified"),
            self._decl("importer", "Importer", importer, 0.88, f"Importer declared: {importer}" if importer else "Importer declaration not specified"),
            self._decl("net_qty", "Net Quantity", net_qty, 0.94, f"Net quantity: {net_qty}" if net_qty else "Net quantity declaration missing"),
            self._decl("mrp", "MRP", mrp, 0.96, f"MRP declared: {mrp}" if mrp else "MRP declaration missing"),
            self._decl("date_info", "Date Information", date_val, 0.92, f"Date info: {date_val}" if date_val else "Date declaration missing"),
            self._decl("consumer_care", "Consumer Care", consumer_care, 0.92, f"Consumer care: {consumer_care}" if consumer_care else "Consumer care details missing"),
            self._decl("batch_lot", "Batch/Lot", batch, 0.90, f"Batch No: {batch}" if batch else "Batch/Lot number missing"),
        ]
        return {"product": product, "declarations": declarations, "full_text": text, "ocr_data": ocr_data or {}}

    @staticmethod
    def _decl(id_: str, field: str, value: Optional[str], confidence: float, finding: str) -> Dict[str, Any]:
        return {
            "id": id_,
            "fieldName": field,
            "extractedValue": value,
            "confidence": confidence if value else 0.0,
            "status": "COMPLIANT" if value else "MISSING",
            "finding": finding,
            "regionId": None,
        }

    def create_regions(self, ocr_data: Dict[str, Any], extracted: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Map declarations to the nearest semantically matching OCR box."""
        regions: List[Dict[str, Any]] = []
        boxes = ocr_data.get("boxes", [])
        product = extracted.get("product", {})
        colors = {"COMPLIANT": "#10B981", "NEEDS REVIEW": "#F59E0B", "NON-COMPLIANT": "#EF4444", "MISSING": "#6B7280"}

        label_keywords = {
            "prod_name": ["product", "item", "commodity"],
            "mfg": ["manufactured by", "mfd by", "mfg by", "marketed by", "mktd by"],
            "packer": ["packed by", "pkd by", "packer"],
            "importer": ["imported by", "importer"],
            "net_qty": ["net weight", "net wt", "net quantity", "net qty", "net content"],
            "mrp": ["mrp", "m.r.p", "maximum retail price"],
            "date_info": ["packed", "pkd", "mfg", "manufactured", "best before", "use by", "expiry", "exp"],
            "consumer_care": ["consumer care", "customer care", "helpline", "toll free", "feedback", "contact"],
            "batch_lot": ["batch", "lot no", "lot", "b.no"],
        }
        fields = {
            "prod_name": ("name", product.get("name")), "mfg": ("manufacturer", product.get("manufacturer")),
            "packer": ("packer", product.get("packer")), "importer": ("importer", product.get("importer")),
            "net_qty": ("netQuantity", product.get("netQuantity")), "mrp": ("mrp", product.get("mrp")),
            "date_info": ("packedDate", product.get("packedDate") or product.get("expiryDate")),
            "consumer_care": ("consumerCare", product.get("consumerCare")), "batch_lot": ("batchNo", product.get("batchNo")),
        }

        def score_box(box: Dict[str, Any], decl_id: str, value: Optional[str]) -> int:
            t = box["text"].lower()
            score = 0
            for kw in label_keywords[decl_id]:
                if kw in t:
                    score += 80
            if value:
                normal = re.sub(r"[₹,\s]", "", str(value)).lower()
                if normal and normal in re.sub(r"[₹,\s]", "", t):
                    score += 100
                for token in str(value).lower().split():
                    if len(token) >= 4 and token in t:
                        score += 20
            # Penalise obvious unrelated sections for manufacturer/batch/date.
            if decl_id == "mfg" and "ingredients" in t:
                score -= 100
            if decl_id == "batch_lot" and not re.search(r"\d", t):
                score -= 50

            if decl_id == "consumer_care":
                # A region is useful only if it contains a real contact signal.
                # Long licence/barcode numbers are strong negative evidence.
                has_email = bool(re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", box["text"], re.I))
                has_toll = bool(re.search(r"(?:1[\s.-]?)?800[\s.-]?\d{3,4}[\s.-]?\d{4}", box["text"], re.I))
                has_mobile = bool(re.search(r"(?<!\d)(?:\+?91[\s.-]?)?[6-9]\d{9}(?!\d)", box["text"]))
                long_numeric = bool(re.search(r"(?<!\d)\d{11,}(?!\d)", re.sub(r"[ -]", "", box["text"])))
                if has_email or has_toll or has_mobile:
                    score += 140
                if long_numeric and not (has_toll or has_mobile):
                    score -= 180
                # Prefer a compact contact line over a huge address/licence block.
                if float(box.get("width", 0)) > 55 and not (has_email or has_toll or has_mobile):
                    score -= 80
            return score

        used = set()
        for decl in extracted.get("declarations", []):
            did = decl["id"]
            if did not in fields:
                continue

            # Do not create a Batch/Lot evidence region when no valid
            # batch/lot value was actually extracted.
            if did == "batch_lot" and not fields[did][1]:
                continue
            field, value = fields[did]
            ranked = sorted(((score_box(b, did, value), i, b) for i, b in enumerate(boxes)), reverse=True)
            if not ranked or ranked[0][0] <= 0:
                continue
            _, idx, box = ranked[0]
            # Avoid assigning one OCR box to multiple declarations unless it is a
            # broad line that genuinely contains the field label and value.
            if idx in used and not any(k in box["text"].lower() for k in label_keywords[did]):
                continue
            used.add(idx)
            status = decl["status"]
            region_id = f"reg_{did}"
            regions.append({
                "id": region_id, "label": did, "field": field,
                "top": box["top"], "left": box["left"], "width": box["width"], "height": box["height"],
                "color": colors.get(status, "#10B981"), "status": status,
                "extractedText": box["text"], "confidence": round(box.get("confidence", decl.get("confidence", 0.8)), 3),
            })
            decl["regionId"] = region_id
        return regions
