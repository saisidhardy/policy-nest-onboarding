"""Local OCR execution, document classification, field normalization, and Aadhaar masking."""

import base64
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import cv2
import pytesseract
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.cv_quality import ImageQualityMetrics, analyze_image_quality, decode_image, extract_pdf_payload
from app.services.http_client import request_json_with_retry
from app.services.platform_config import EffectiveIntegrationsConfig, get_effective_integrations_config

PAN_CANDIDATE_RE = re.compile(r"\b([A-Z]{5}[0-9OIlS]{4}[A-Z])\b")
PAN_STRICT_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
IFSC_RE = re.compile(r"\b([A-Z]{4}[0O][A-Z0-9]{6})\b")
AADHAAR_12_RE = re.compile(r"\b(\d{4})[\s\-]?(\d{4})[\s\-]?(\d{4})\b")
PINCODE_RE = re.compile(r"\b([1-9]\d{5})\b")
DATE_DMY_RE = re.compile(r"\b(\d{2})[/\-.](\d{2})[/\-.](\d{4})\b")
DATE_YMD_RE = re.compile(r"\b(\d{4})[/\-.](\d{2})[/\-.](\d{2})\b")
YEAR_RE = re.compile(r"\b(19[5-9]\d|20[0-2]\d)\b")
ACCOUNT_NUM_RE = re.compile(r"(?:A/C|ACCOUNT|ACCT|ACC)\s*(?:NO\.?|NUMBER|#)?[:\-\s]*(\d{9,18})\b", re.I)

HONORIFICS = {"MR", "MRS", "MS", "MISS", "SHRI", "SMT", "KUMARI", "DR"}

EXPECTED_FIELDS_BY_DOC: dict[str, list[str]] = {
    "PAN_CARD": ["pan_number", "full_name", "dob"],
    "AADHAAR_FRONT": ["full_name", "dob", "aadhaar_last4"],
    "AADHAAR_BACK": ["address_or_pincode"],
    "CLASS_10_MARKSHEET": ["full_name", "board_name", "result_status"],
    "BANK_DOCUMENT": ["ifsc_code", "account_last4"],
    "APPLICANT_SELFIE": ["face_detected"],
}


@dataclass(frozen=True)
class OcrPipelineResult:
    ocr_engine: str
    quality: ImageQualityMetrics
    ocr_confidence: float | None
    raw_ocr_text_masked: str
    predicted_doc_type: str
    classification_confidence: float
    classification_match: bool
    extracted_fields: dict[str, str]
    missing_fields: list[str]
    aadhaar_masked_applied: bool
    redacted_image_bytes: bytes | None


def resolve_tesseract_cmd() -> str | None:
    s = get_settings()
    if s.tesseract_cmd and Path(s.tesseract_cmd).is_file():
        return s.tesseract_cmd
    which = shutil.which("tesseract")
    if which:
        return which
    win_default = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    if win_default.is_file():
        return str(win_default)
    return None


def mask_aadhaar_numbers_in_text(text: str) -> tuple[str, list[str]]:
    """Mask any 12-digit Aadhaar sequence as XXXX-XXXX-<last4> before persistence."""
    found_last4: list[str] = []

    def _repl(match: re.Match[str]) -> str:
        prefix = text[max(0, match.start() - 18) : match.start()].upper()
        if any(tok in prefix for tok in ("A/C", "ACC", "ACCOUNT", "ROLL")):
            return match.group(0)
        last4 = match.group(3)
        found_last4.append(last4)
        return f"XXXX-XXXX-{last4}"

    masked = AADHAAR_12_RE.sub(_repl, text)
    return masked, found_last4


def normalize_person_name(raw: str | None) -> str | None:
    if not raw:
        return None
    cleaned = re.sub(r"[^A-Za-z.\s]", " ", raw).upper()
    tokens = [t.strip(".") for t in cleaned.split() if t.strip(".")]
    while tokens and tokens[0] in HONORIFICS:
        tokens.pop(0)
    if not tokens:
        return None
    return " ".join(tokens)


def normalize_date_str(raw: str | None) -> str | None:
    if not raw:
        return None
    s = raw.strip()
    if m := DATE_YMD_RE.search(s):
        try:
            dt = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass
    if m := DATE_DMY_RE.search(s):
        try:
            dt = datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass
    if re.fullmatch(r"(19\d{2}|20[0-2]\d)", s):
        return s
    return None


def _normalize_pan_ocr(candidate: str) -> str:
    chars = list(candidate.upper())
    digit_fix = {"O": "0", "Q": "0", "I": "1", "L": "1", "S": "5", "B": "8", "Z": "2"}
    for idx in range(5, 9):
        if chars[idx] in digit_fix:
            chars[idx] = digit_fix[chars[idx]]
    return "".join(chars)


def _normalize_ifsc_ocr(candidate: str) -> str:
    chars = list(candidate.upper())
    if len(chars) == 11 and chars[4] == "O":
        chars[4] = "0"
    return "".join(chars)


def classify_document(text: str, *, has_face: bool = False) -> tuple[str, float]:
    up = re.sub(r"\s+", " ", text.upper()).strip()
    scores: dict[str, float] = {
        "PAN_CARD": 0.0,
        "AADHAAR_FRONT": 0.0,
        "AADHAAR_BACK": 0.0,
        "CLASS_10_MARKSHEET": 0.0,
        "BANK_DOCUMENT": 0.0,
        "APPLICANT_SELFIE": 0.0,
    }
    pan_header = any(
        k in up
        for k in ("INCOME TAX", "INCOMETAX", "TAX DEPARTMENT", "PERMANENT ACCOUNT", "NSDL", "PROTEAN", "E-PAN")
    )
    if pan_header:
        scores["PAN_CARD"] += 0.65
    if PAN_CANDIDATE_RE.search(up):
        scores["PAN_CARD"] += 0.45

    aadhaar_generic = any(
        k in up for k in ("AADHAAR", "UIDAI", "UNIQUE IDENTIFICATION", "MERA AADHAAR", "XXXX-XXXX-", "VID")
    ) or bool(AADHAAR_12_RE.search(up))
    aadhaar_front_cues = bool(
        re.search(r"\b(DOB|D\.O\.B|YOB|YEAR OF BIRTH|MALE|FEMALE|TRANSGENDER|PURUSH|MAHILA)\b", up)
    )
    aadhaar_back_rel = bool(re.search(r"\b(S/O|D/O|W/O|C/O)\b", up))
    aadhaar_back_addr = any(
        k in up for k in ("ADDRESS", "HELP@UIDAI", "UIDAI.GOV.IN", "1947", "POST OFFICE", "P.O.", "DISTRICT")
    )
    has_pincode = bool(PINCODE_RE.search(up))
    aadhaar_back_cues = (
        aadhaar_back_addr
        or aadhaar_back_rel
        or (aadhaar_generic and has_pincode and "PIN" in up)
        or (aadhaar_generic and has_pincode and not aadhaar_front_cues)
    )

    if aadhaar_generic:
        scores["AADHAAR_FRONT"] += 0.35
        scores["AADHAAR_BACK"] += 0.35
    if aadhaar_front_cues and not pan_header and (aadhaar_generic or not any(
        k in up for k in ("MARKSHEET", "BOARD OF", "EXAMINATION", "CHEQUE", "IFSC")
    )):
        scores["AADHAAR_FRONT"] += 0.35
    if aadhaar_generic and has_face and not aadhaar_back_cues and not pan_header:
        scores["AADHAAR_FRONT"] += 0.20
    if aadhaar_back_cues:
        scores["AADHAAR_BACK"] += 0.45
        if has_pincode:
            scores["AADHAAR_BACK"] += 0.10

    if any(
        k in up
        for k in (
            "CBSE",
            "CISCE",
            "ICSE",
            "NIOS",
            "SSC",
            "SSLC",
            "MATRIC",
            "SECONDARY",
            "SEEONVARY",
            "MARKSHEET",
            "MARK SHEET",
            "STATEMENT OF MARKS",
            "CLASS X",
            "HIGH SCHOOL",
            "BOARD OF",
            "EXAMINATION",
        )
    ):
        scores["CLASS_10_MARKSHEET"] += 0.60
    if any(k in up for k in ("ROLL", "SUBJECT", "MARKS", "GRADE", "SCHOOL", "CGPA", "GPA", "PASS", "DIVISION")):
        scores["CLASS_10_MARKSHEET"] += 0.25

    bank_kw = bool(
        re.search(
            r"\b(IFSC|MICR|CANCELLED|CHEQUE|BANK|BRANCH|PASSBOOK|SAVINGS|A/C|PAYEE|NEFT|RTGS|IMPS|STATEMENT)\b",
            up,
        )
    ) or any(k in up for k in ("ACCOUNT HOLDER", "ACCOUNT NO", "ACCOUNT NUMBER", "ACCT NO"))
    if bank_kw:
        scores["BANK_DOCUMENT"] += 0.50
    if IFSC_RE.search(up):
        scores["BANK_DOCUMENT"] += 0.40
    if ACCOUNT_NUM_RE.search(up):
        scores["BANK_DOCUMENT"] += 0.20

    other_best = max(v for k, v in scores.items() if k != "APPLICANT_SELFIE")
    if has_face and (len(up) < 60 or other_best < 0.30):
        scores["APPLICANT_SELFIE"] = 0.85

    best_type, best_score = max(scores.items(), key=lambda kv: kv[1])
    if best_score < 0.30:
        return "UNKNOWN", round(best_score, 2)
    return best_type, round(min(1.0, best_score), 2)


def _extract_labeled_name(text: str) -> str | None:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for idx, line in enumerate(lines):
        m = re.search(r"(?:^|\b)(?:NAME|HOLDER|CANDIDATE\s*NAME)\s*[:\-]\s*(.+)$", line, re.I)
        if m:
            candidate = m.group(1).strip()
            if len(candidate) >= 3 and not re.search(r"FATHER|MOTHER", line, re.I):
                norm = normalize_person_name(candidate)
                if norm:
                    return norm
        if re.fullmatch(r"(?:NAME|CANDIDATE\s*NAME)[:\-]?", line, re.I) and idx + 1 < len(lines):
            norm = normalize_person_name(lines[idx + 1])
            if norm:
                return norm
    # Fallback for Aadhaar front lines immediately preceding DOB
    for idx, line in enumerate(lines):
        if re.search(r"(?:DOB|D\.O\.B|BIRTH|जन्म)", line, re.I) and idx > 0:
            prev = lines[idx - 1]
            if not any(w in prev.upper() for w in ("GOVERNMENT", "INDIA", "UNIQUE", "AADHAAR")):
                norm = normalize_person_name(prev)
                if norm and len(norm.split()) >= 2:
                    return norm
    return None


def _extract_father_name(text: str) -> str | None:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for idx, line in enumerate(lines):
        m = re.search(r"(?:FATHER(?:'S)?\s*NAME|S/O|D/O)\s*(?:[:\-]\s*|\s+)([A-Za-z][A-Za-z\s\.]{2,})$", line, re.I)
        if m:
            norm = normalize_person_name(m.group(1))
            if norm and len(norm) >= 4:
                return norm
        if re.search(r"FATHER(?:'S)?\s*NAME", line, re.I):
            for offset in (1, 2):
                if idx + offset < len(lines):
                    cand = lines[idx + offset]
                    if re.search(r"^\s*MOTHER", cand, re.I):
                        continue
                    norm = normalize_person_name(cand)
                    if norm and len(norm) >= 4 and len(norm.split()) >= 2:
                        return norm
    return None


def extract_fields_for_doc(
    doc_type: str, masked_text: str, *, face_detected: bool | None = None
) -> tuple[dict[str, str], list[str]]:
    up = masked_text.upper()
    fields: dict[str, str] = {}

    name = _extract_labeled_name(masked_text)
    if name:
        fields["full_name"] = name

    father = _extract_father_name(masked_text)
    if father:
        fields["father_name"] = father

    # Dates
    for line in masked_text.splitlines():
        if any(k in line.upper() for k in ("DOB", "BIRTH", "D.O.B")) or doc_type in (
            "PAN_CARD",
            "AADHAAR_FRONT",
            "CLASS_10_MARKSHEET",
        ):
            norm_dt = normalize_date_str(line)
            if norm_dt:
                fields["dob"] = norm_dt
                break
    if "dob" not in fields and doc_type == "AADHAAR_FRONT":
        if m := re.search(r"(?:YEAR\s*OF\s*BIRTH|YOB)\s*[:\-]?\s*(19\d{2}|20[0-2]\d)", up):
            fields["dob"] = m.group(1)

    if doc_type == "PAN_CARD":
        if m := PAN_CANDIDATE_RE.search(up):
            pan = _normalize_pan_ocr(m.group(1))
            if PAN_STRICT_RE.match(pan):
                fields["pan_number"] = pan

    if doc_type in ("AADHAAR_FRONT", "AADHAAR_BACK"):
        if m := re.search(r"XXXX-XXXX-(\d{4})", up):
            fields["aadhaar_last4"] = m.group(1)
        elif m := re.search(r"\b(\d{4})\b(?=[^\d]*$)", up.strip()):
            fields["aadhaar_last4"] = m.group(1)
        if "FEMALE" in up:
            fields["gender"] = "FEMALE"
        elif "MALE" in up:
            fields["gender"] = "MALE"
        if m := PINCODE_RE.search(up):
            fields["pincode"] = m.group(1)
        if doc_type == "AADHAAR_BACK" and (
            "pincode" in fields or any(k in up for k in ("ADDRESS", "ROAD", "NAGAR", "CITY", "DIST"))
        ):
            fields["address_or_pincode"] = fields.get("pincode", "ADDRESS_TEXT_DETECTED")

    if doc_type == "CLASS_10_MARKSHEET":
        for board in ("CBSE", "CISCE", "ICSE", "NIOS"):
            if board in up:
                fields["board_name"] = board
                break
        if "board_name" not in fields and "BOARD" in up:
            fields["board_name"] = "STATE_BOARD"
        if "PASS" in up or "PASSED" in up:
            fields["result_status"] = "PASS"
        elif "FAIL" in up:
            fields["result_status"] = "FAIL"
        if m := re.search(r"ROLL\s*(?:NO\.?|NUMBER)?\s*[:\-]?\s*([A-Z0-9\-]{4,20})", up):
            fields["roll_number"] = m.group(1)
        if m := YEAR_RE.search(up):
            fields["passing_year"] = m.group(1)

    if doc_type == "BANK_DOCUMENT":
        if m := IFSC_RE.search(up):
            fields["ifsc_code"] = _normalize_ifsc_ocr(m.group(1))
        if m := ACCOUNT_NUM_RE.search(masked_text):
            fields["account_last4"] = m.group(1)[-4:]
        elif m := re.search(r"\b\d{9,18}\b", up):
            fields["account_last4"] = m.group(0)[-4:]

    if doc_type == "APPLICANT_SELFIE" and face_detected is not None:
        fields["face_detected"] = "true" if face_detected else "false"

    expected = EXPECTED_FIELDS_BY_DOC.get(doc_type, [])
    missing = [f for f in expected if not fields.get(f) or (f == "face_detected" and fields[f] != "true")]
    return fields, missing


def _redact_aadhaar_image(image_bytes: bytes, ocr_data: dict | None) -> bytes | None:
    """Redact detected 12-digit Aadhaar number boxes and QR code via solid OpenCV black rectangles."""
    img = decode_image(image_bytes)
    if img is None:
        return None
    redacted = img.copy()

    # Redact QR codes if detectable
    detector = cv2.QRCodeDetector()
    ok, pts = detector.detect(redacted)
    if ok and pts is not None:
        for poly in pts:
            xs = [int(p[0]) for p in poly]
            ys = [int(p[1]) for p in poly]
            cv2.rectangle(redacted, (min(xs), min(ys)), (max(xs), max(ys)), (0, 0, 0), -1)

    # Redact 4-4-4 or 12-digit numeric boxes
    if ocr_data and "text" in ocr_data:
        words = ocr_data["text"]
        n = len(words)
        for i, w in enumerate(words):
            clean = re.sub(r"\D", "", str(w))
            if len(clean) == 12:
                x, y, bw, bh = ocr_data["left"][i], ocr_data["top"][i], ocr_data["width"][i], ocr_data["height"][i]
                cv2.rectangle(redacted, (x, y), (x + int(bw * 0.68), y + bh), (0, 0, 0), -1)
            elif i + 2 < n and len(clean) == 4:
                c2 = re.sub(r"\D", "", str(words[i + 1]))
                c3 = re.sub(r"\D", "", str(words[i + 2]))
                if len(c2) == 4 and len(c3) == 4:
                    for idx in (i, i + 1):
                        x, y, bw, bh = (
                            ocr_data["left"][idx],
                            ocr_data["top"][idx],
                            ocr_data["width"][idx],
                            ocr_data["height"][idx],
                        )
                        cv2.rectangle(redacted, (x, y), (x + bw, y + bh), (0, 0, 0), -1)

    ok_enc, buf = cv2.imencode(".png", redacted)
    return bytes(buf) if ok_enc else None


def _tesseract_pass(gray_img) -> tuple[str, float, dict]:
    data = pytesseract.image_to_data(gray_img, output_type=pytesseract.Output.DICT)
    words = [str(w).strip() for w in data.get("text", [])]
    confs = []
    for w, c in zip(words, data.get("conf", []), strict=False):
        try:
            cv = float(c)
        except (TypeError, ValueError):
            continue
        if w and cv >= 0:
            confs.append(cv / 100.0)
    raw_text = pytesseract.image_to_string(gray_img)
    avg_conf = round(sum(confs) / len(confs), 3) if confs else 0.0
    return raw_text, avg_conf, data


def _run_tesseract_on_image(image_bytes: bytes) -> tuple[str, float | None, dict | None, str]:
    s = get_settings()
    if s.ocr_provider == "none":
        return "", None, None, "OCR_DISABLED"
    cmd = resolve_tesseract_cmd()
    if not cmd:
        return "", None, None, "OCR_UNAVAILABLE"

    pytesseract.pytesseract.tesseract_cmd = cmd
    img = decode_image(image_bytes)
    if img is None:
        return "", 0.0, None, "LOCAL_TESSERACT"

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    raw_text, avg_conf, data = _tesseract_pass(gray)

    # Fallback auto-rotation for sideways/upside-down mobile uploads
    if len(re.sub(r"\s+", "", raw_text)) < 25 or avg_conf < 0.40:
        h, w = gray.shape[:2]
        probe = gray
        if max(h, w) > 1200:
            scale = 1200.0 / float(max(h, w))
            probe = cv2.resize(gray, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
        best_score = (avg_conf * 100.0) + min(40, len(re.sub(r"\s+", "", raw_text)))
        best_rot: int | None = None
        for rot_code in (cv2.ROTATE_90_CLOCKWISE, cv2.ROTATE_90_COUNTERCLOCKWISE, cv2.ROTATE_180):
            rot_probe = cv2.rotate(probe, rot_code)
            txt = pytesseract.image_to_string(rot_probe)
            clean_len = len(re.sub(r"\s+", "", txt))
            if clean_len >= 25:
                cand_conf = 65.0 + min(40, clean_len)
                if cand_conf > best_score:
                    best_score = cand_conf
                    best_rot = rot_code
        if best_rot is not None:
            raw_text, avg_conf, data = _tesseract_pass(cv2.rotate(gray, best_rot))

    return raw_text, avg_conf, data, "LOCAL_TESSERACT"


def _run_http_ocr(
    doc_type: str, content_type: str, data: bytes, cfg: EffectiveIntegrationsConfig
) -> tuple[str, float | None, dict | None, str]:
    if not cfg.ocr_api_base_url or not cfg.ocr_api_key:
        return "", None, None, "HTTP_OCR_UNCONFIGURED"
    res = request_json_with_retry(
        "POST",
        cfg.ocr_api_base_url,
        headers={"Authorization": f"Bearer {cfg.ocr_api_key}", "Content-Type": "application/json"},
        json_body={
            "doc_type": doc_type,
            "content_type": content_type,
            "content_base64": base64.b64encode(data).decode("ascii"),
        },
        timeout_seconds=float(cfg.integration_http_timeout_seconds),
        max_retries=cfg.integration_http_max_retries,
        backoff_base_seconds=0.1,
    )
    if not res.ok:
        return "", None, None, "HTTP_OCR_UNAVAILABLE"
    text = str(res.data.get("text") or "")
    raw_conf = res.data.get("confidence")
    conf = float(raw_conf) if isinstance(raw_conf, int | float) else None
    return text, conf, None, "HTTP_OCR"


def process_document_bytes(
    doc_type: str, content_type: str, data: bytes, db: Session | None = None
) -> OcrPipelineResult:
    """Run CV quality inspection, configured OCR (local Tesseract or HTTP OCR), normalization, and Aadhaar masking."""
    cfg = get_effective_integrations_config(db)
    is_pdf = content_type == "application/pdf"
    is_selfie = doc_type == "APPLICANT_SELFIE"

    raw_text = ""
    ocr_confidence: float | None = None
    ocr_engine = "LOCAL_TESSERACT"
    ocr_data: dict | None = None
    raster_for_redaction: bytes | None = None

    if is_pdf:
        pdf_text, pdf_images = extract_pdf_payload(data)
        if pdf_text:
            raw_text = pdf_text
            ocr_confidence = 0.95
            ocr_engine = "PYPDF_TEXT"
            quality = ImageQualityMetrics("OK", None, None, None, False if is_selfie else None, None, None)
        elif pdf_images:
            raster_for_redaction = pdf_images[0]
            quality = analyze_image_quality(raster_for_redaction, check_face=is_selfie, detect_face=not is_selfie)
            if cfg.ocr_provider == "none":
                ocr_engine = "DISABLED"
            elif cfg.ocr_provider == "http_ocr":
                raw_text, ocr_confidence, ocr_data, ocr_engine = _run_http_ocr(
                    doc_type, "image/png", raster_for_redaction, cfg
                )
            else:
                raw_text, ocr_confidence, ocr_data, ocr_engine = _run_tesseract_on_image(raster_for_redaction)
        else:
            quality = ImageQualityMetrics("UNREADABLE", None, None, None, False if is_selfie else None, None, None)
            ocr_confidence = 0.0
            ocr_engine = "PYPDF_TEXT"
    else:
        raster_for_redaction = data
        quality = analyze_image_quality(data, check_face=is_selfie, detect_face=not is_selfie)
        if is_selfie:
            ocr_engine = "CV_FACE_DETECTOR"
            ocr_confidence = 1.0 if quality.face_detected else 0.0
            if quality.width is not None and quality.quality_status != "UNREADABLE" and cfg.ocr_provider == "local_tesseract":
                raw_text, _, _, _ = _run_tesseract_on_image(data)
        elif cfg.ocr_provider == "none":
            ocr_engine = "DISABLED"
        elif cfg.ocr_provider == "http_ocr":
            raw_text, ocr_confidence, ocr_data, ocr_engine = _run_http_ocr(doc_type, content_type, data, cfg)
        else:
            raw_text, ocr_confidence, ocr_data, ocr_engine = _run_tesseract_on_image(data)

    masked_text, aadhaar_last4_hits = mask_aadhaar_numbers_in_text(raw_text)
    aadhaar_applied = doc_type in ("AADHAAR_FRONT", "AADHAAR_BACK") or bool(aadhaar_last4_hits)

    redacted_bytes: bytes | None = None
    if doc_type in ("AADHAAR_FRONT", "AADHAAR_BACK") and raster_for_redaction is not None:
        redacted_bytes = _redact_aadhaar_image(raster_for_redaction, ocr_data)
        aadhaar_applied = True

    if is_selfie:
        ocr_pred, ocr_conf = classify_document(masked_text, has_face=bool(quality.face_detected))
        if ocr_pred not in ("UNKNOWN", "APPLICANT_SELFIE") and ocr_conf >= 0.55:
            predicted_type, class_conf = ocr_pred, ocr_conf
        else:
            predicted_type = "APPLICANT_SELFIE" if quality.face_detected else "UNKNOWN"
            class_conf = 0.95 if quality.face_detected else 0.2
    else:
        predicted_type, class_conf = classify_document(masked_text, has_face=bool(quality.face_detected))

    classification_match = predicted_type == doc_type
    fields, missing = extract_fields_for_doc(doc_type, masked_text, face_detected=quality.face_detected)

    # Low OCR confidence on clear image still warns quality if unreadable
    if not is_selfie and ocr_engine == "LOCAL_TESSERACT" and quality.quality_status == "OK":
        if ocr_confidence is not None and ocr_confidence < 0.45 and len(masked_text.strip()) < 15:
            quality = ImageQualityMetrics(
                quality_status="IMAGE_BLURRY",
                blur_score=quality.blur_score,
                glare_ratio=quality.glare_ratio,
                edge_clip_ratio=quality.edge_clip_ratio,
                face_detected=quality.face_detected,
                width=quality.width,
                height=quality.height,
            )

    return OcrPipelineResult(
        ocr_engine=ocr_engine,
        quality=quality,
        ocr_confidence=ocr_confidence,
        raw_ocr_text_masked=masked_text,
        predicted_doc_type=predicted_type,
        classification_confidence=class_conf,
        classification_match=classification_match,
        extracted_fields=fields,
        missing_fields=missing,
        aadhaar_masked_applied=aadhaar_applied,
        redacted_image_bytes=redacted_bytes,
    )
