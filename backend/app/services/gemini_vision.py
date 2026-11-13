"""Multimodal Gemini Vision OCR, document classification, quality inspection, and advisory face comparison."""

from __future__ import annotations

import base64
import logging
import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

from app.services.platform_config import EffectiveIntegrationsConfig

logger = logging.getLogger(__name__)

_MASKED_12_RE = re.compile(r"(?<!\d)(\d{4})[\s\-]?(\d{4})[\s\-]?(\d{4})(?!\d)")

DocLabel = Literal[
    "PAN_CARD",
    "AADHAAR_FRONT",
    "AADHAAR_BACK",
    "CLASS_10_MARKSHEET",
    "BANK_DOCUMENT",
    "APPLICANT_SELFIE",
    "UNKNOWN",
]


class _GeminiDocFields(BaseModel):
    full_name: str | None = Field(default=None, description="Applicant full name shown on the document.")
    father_name: str | None = Field(default=None, description="Father/mother/guardian name if printed.")
    dob: str | None = Field(default=None, description="Date of birth or year of birth (YYYY-MM-DD or YYYY).")
    pan_number: str | None = Field(default=None, description="10-character PAN number in AAAAA9999A format.")
    aadhaar_last4: str | None = Field(default=None, description="ONLY the last 4 digits of Aadhaar number (never all 12 digits).")
    gender: str | None = Field(default=None, description="MALE, FEMALE, or OTHER if visible.")
    pincode: str | None = Field(default=None, description="6-digit Indian postal PIN code.")
    state: str | None = Field(default=None, description="Indian state name from address if visible.")
    address_summary: str | None = Field(default=None, description="Short address snippet without sensitive Aadhaar digits.")
    board_name: str | None = Field(default=None, description="Education board (e.g. CBSE, ICSE, CISCE, NIOS, or state board).")
    school_or_university: str | None = Field(default=None, description="School/board institution name on marksheet.")
    roll_number: str | None = Field(default=None, description="Roll number or registration number on marksheet.")
    passing_year: str | None = Field(default=None, description="4-digit passing year.")
    result_status: str | None = Field(default=None, description="PASS, FAIL, or COMPARTMENT.")
    ifsc_code: str | None = Field(default=None, description="11-character bank IFSC code.")
    account_last4: str | None = Field(default=None, description="ONLY the last 4 digits of bank account number.")
    bank_name: str | None = Field(default=None, description="Bank name printed on cheque, passbook, or statement.")


class _GeminiDocExtractionSchema(BaseModel):
    predicted_doc_type: DocLabel = Field(description="Detected Indian KYC document type.")
    classification_confidence: float = Field(ge=0.0, le=1.0, description="Confidence 0-1 for document type.")
    is_valid_document: bool = Field(description="True if this is a genuine readable KYC document/photo matching its visual layout.")
    is_blurry: bool = Field(default=False, description="True if text or portrait is too blurry to verify reliably.")
    has_heavy_glare: bool = Field(default=False, description="True if flash glare obscures key fields.")
    is_cropped: bool = Field(default=False, description="True if critical document edges or fields are cut off.")
    appears_blank_or_fake: bool = Field(default=False, description="True if blank, placeholder, non-document image, or obvious template tampering.")
    face_detected: bool | None = Field(default=None, description="True if a human face or portrait photo is clearly visible.")
    ocr_confidence: float = Field(ge=0.0, le=1.0, description="Overall readability/OCR confidence 0-1.")
    transcribed_text_masked: str = Field(
        default="",
        description="Key visible text from the document, with the first 8 digits of any 12-digit Aadhaar replaced by XXXX-XXXX-.",
    )
    quality_feedback: str = Field(default="", description="Concise 1-2 sentence assessment of legibility and validity.")
    fields: _GeminiDocFields = Field(default_factory=_GeminiDocFields)


class _GeminiFaceCompareSchema(BaseModel):
    selfie_has_clear_face: bool = Field(description="True if applicant selfie contains one clear frontal human face.")
    aadhaar_face_detected: bool = Field(default=False, description="True if portrait photo is visible on Aadhaar front.")
    aadhaar_match_score: float | None = Field(default=None, ge=0.0, le=1.0, description="Visual similarity 0-1 between selfie and Aadhaar photo.")
    pan_face_detected: bool = Field(default=False, description="True if portrait photo is visible on PAN card.")
    pan_match_score: float | None = Field(default=None, ge=0.0, le=1.0, description="Visual similarity 0-1 between selfie and PAN card photo.")
    overall_match_score: float | None = Field(default=None, ge=0.0, le=1.0, description="Overall visual match confidence 0-1.")
    verdict: Literal["MATCH", "UNCERTAIN", "MISMATCH", "UNABLE"] = Field(description="Visual face comparison verdict.")
    reasoning: str = Field(description="Brief visual observation (non-biometric advisory note).")


@dataclass(frozen=True)
class GeminiVisionDocResult:
    predicted_doc_type: str
    classification_confidence: float
    is_valid_document: bool
    is_blurry: bool
    has_heavy_glare: bool
    is_cropped: bool
    appears_blank_or_fake: bool
    face_detected: bool | None
    ocr_confidence: float
    raw_text_masked: str
    quality_feedback: str
    raw_fields: dict[str, str]


@dataclass(frozen=True)
class GeminiFaceCompareResult:
    selfie_has_clear_face: bool
    aadhaar_face_detected: bool
    aadhaar_match_score: float | None
    pan_face_detected: bool
    pan_match_score: float | None
    overall_match_score: float | None
    verdict: str
    reasoning: str


def _mask_sensitive_text(text: str) -> str:
    return _MASKED_12_RE.sub(lambda m: f"XXXX-XXXX-{m.group(3)}", text or "")


def _media_part(mime_type: str, raw_bytes: bytes) -> dict[str, str]:
    encoded = base64.b64encode(raw_bytes).decode("ascii")
    part_type = "document" if mime_type == "application/pdf" else "image"
    return {"type": part_type, "data": encoded, "mime_type": mime_type}


def _create_genai_client(genai_mod, api_key: str):
    try:
        from google.genai import types

        retry_opts = getattr(types, "HttpRetryOptions", None)
        if retry_opts is not None:
            return genai_mod.Client(
                api_key=api_key,
                http_options=types.HttpOptions(timeout=12000, retry_options=retry_opts(attempts=2)),
            )
        return genai_mod.Client(api_key=api_key, http_options=types.HttpOptions(timeout=12000))
    except TypeError:
        return genai_mod.Client(api_key=api_key)


def _to_generate_content_parts(input_data, types_mod):
    if isinstance(input_data, str):
        return input_data
    parts = []
    for item in input_data:
        if isinstance(item, dict):
            if item.get("type") == "text":
                parts.append(item.get("text", ""))
            elif "data" in item and "mime_type" in item:
                parts.append(
                    types_mod.Part.from_bytes(
                        data=base64.b64decode(item["data"]),
                        mime_type=item["mime_type"],
                    )
                )
        else:
            parts.append(item)
    return parts


def run_gemini_interaction(
    *,
    api_key: str,
    primary_model: str,
    input_data,
    schema: dict,
) -> str | None:
    """Execute a structured Gemini multimodal request with fast Flash-Lite fallback."""
    from google import genai
    from google.genai import types

    client = _create_genai_client(genai, api_key)
    models_api = getattr(client, "models", None)
    candidates: list[str] = []
    for m in (
        primary_model,
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-3.8-flash",
        "gemini-3.5-flash-lite",
        "gemini-3.7-flash",
        "gemini-3.6-flash",
        "gemini-3.1-flash-lite",
    ):
        if m and m not in candidates:
            candidates.append(m)

    last_exc: Exception | None = None
    for idx, model_name in enumerate(candidates):
        try:
            if models_api is not None:
                resp = models_api.generate_content(
                    model=model_name,
                    contents=_to_generate_content_parts(input_data, types),
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_json_schema=schema,
                    ),
                )
                raw_out = (getattr(resp, "text", None) or "").strip()
            else:
                interaction = client.interactions.create(
                    model=model_name,
                    input=input_data,
                    response_format={
                        "type": "text",
                        "mime_type": "application/json",
                        "schema": schema,
                    },
                    store=False,
                )
                raw_out = (interaction.output_text or "").strip()
            if raw_out:
                return raw_out
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if idx + 1 < len(candidates):
                logger.info("Gemini model %s failed (%s); falling back to %s.", model_name, exc.__class__.__name__, candidates[idx + 1])
                continue
    if last_exc is not None:
        raise last_exc
    return None


def extract_document_with_gemini_vision(
    *,
    expected_doc_type: str,
    content_type: str,
    raw_bytes: bytes,
    cfg: EffectiveIntegrationsConfig,
) -> GeminiVisionDocResult | None:
    """Use Gemini multimodal Interactions API to classify, inspect legibility, and extract Indian KYC fields."""
    if not cfg.gemini_api_key:
        return None
    if len(raw_bytes) > 15 * 1024 * 1024:
        return None

    try:
        import google.genai  # noqa: F401
    except Exception:  # noqa: BLE001
        logger.warning("google-genai SDK is unavailable for multimodal document extraction.")
        return None

    prompt = (
        "You are an Indian POSP insurance KYC document verifier and OCR extractor.\n"
        f"The applicant uploaded this file into slot: {expected_doc_type}.\n"
        "Inspect the visual document carefully and return JSON matching the schema:\n"
        "1. Classify the actual document as PAN_CARD, AADHAAR_FRONT, AADHAAR_BACK, "
        "CLASS_10_MARKSHEET, BANK_DOCUMENT, APPLICANT_SELFIE, or UNKNOWN.\n"
        "2. Check if the document is genuinely legible or defective (blurry, glare, cropped, blank, screenshot/fake).\n"
        "3. Extract all readable fields accurately.\n"
        "SECURITY RULE: Never write full 12-digit Aadhaar numbers anywhere. Return ONLY aadhaar_last4 (4 digits) "
        "and mask the first 8 digits as XXXX-XXXX-1234 in transcribed_text_masked."
    )

    try:
        raw_out = run_gemini_interaction(
            api_key=cfg.gemini_api_key,
            primary_model=cfg.gemini_model,
            input_data=[
                _media_part(content_type, raw_bytes),
                {"type": "text", "text": prompt},
            ],
            schema=_GeminiDocExtractionSchema.model_json_schema(),
        )
        if not raw_out:
            return None
        parsed = _GeminiDocExtractionSchema.model_validate_json(raw_out)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Gemini multimodal extraction failed (%s): %s", expected_doc_type, exc.__class__.__name__)
        return None

    fields_dict: dict[str, str] = {}
    raw_model = parsed.fields.model_dump()
    for k, v in raw_model.items():
        if v is None:
            continue
        cleaned = _mask_sensitive_text(str(v).strip())
        if not cleaned or cleaned.lower() in ("null", "none", "n/a"):
            continue
        if k == "aadhaar_last4":
            digits = re.sub(r"\D", "", cleaned)
            if len(digits) >= 4:
                fields_dict["aadhaar_last4"] = digits[-4:]
        elif k == "account_last4":
            digits = re.sub(r"\D", "", cleaned)
            if len(digits) >= 4:
                fields_dict["account_last4"] = digits[-4:]
        elif k == "address_summary":
            fields_dict["address_summary"] = cleaned[:160]
            fields_dict["address_or_pincode"] = fields_dict.get("pincode") or cleaned[:120]
        else:
            fields_dict[k] = cleaned

    return GeminiVisionDocResult(
        predicted_doc_type=parsed.predicted_doc_type,
        classification_confidence=round(float(parsed.classification_confidence), 3),
        is_valid_document=bool(parsed.is_valid_document),
        is_blurry=bool(parsed.is_blurry),
        has_heavy_glare=bool(parsed.has_heavy_glare),
        is_cropped=bool(parsed.is_cropped),
        appears_blank_or_fake=bool(parsed.appears_blank_or_fake),
        face_detected=parsed.face_detected,
        ocr_confidence=round(float(parsed.ocr_confidence), 3),
        raw_text_masked=_mask_sensitive_text(parsed.transcribed_text_masked),
        quality_feedback=_mask_sensitive_text(parsed.quality_feedback),
        raw_fields=fields_dict,
    )


def compare_faces_with_gemini_vision(
    *,
    selfie_bytes: bytes,
    selfie_mime: str,
    aadhaar_bytes: bytes | None = None,
    aadhaar_mime: str | None = None,
    pan_bytes: bytes | None = None,
    pan_mime: str | None = None,
    cfg: EffectiveIntegrationsConfig,
) -> GeminiFaceCompareResult | None:
    """Compare applicant selfie visually against Aadhaar front and/or PAN card portraits using Gemini Vision."""
    if not cfg.gemini_api_key or (aadhaar_bytes is None and pan_bytes is None):
        return None

    try:
        import google.genai  # noqa: F401
    except Exception:  # noqa: BLE001
        return None

    parts: list[dict[str, str]] = [
        {"type": "text", "text": "Image 1: Applicant Live Selfie."},
        _media_part(selfie_mime, selfie_bytes),
    ]
    idx = 2
    if aadhaar_bytes is not None and aadhaar_mime:
        parts.append({"type": "text", "text": f"Image {idx}: Aadhaar Front document containing ID portrait photo."})
        parts.append(_media_part(aadhaar_mime, aadhaar_bytes))
        idx += 1
    if pan_bytes is not None and pan_mime:
        parts.append({"type": "text", "text": f"Image {idx}: PAN Card document containing ID portrait photo."})
        parts.append(_media_part(pan_mime, pan_bytes))

    parts.append(
        {
            "type": "text",
            "text": (
                "Compare the applicant selfie facial structure against each ID card portrait photo present. "
                "Account for normal aging or print lighting differences on Indian ID cards, but flag clear mismatches "
                "or missing/obscured portraits. Return JSON matching the schema."
            ),
        }
    )

    try:
        raw_out = run_gemini_interaction(
            api_key=cfg.gemini_api_key,
            primary_model=cfg.gemini_model,
            input_data=parts,
            schema=_GeminiFaceCompareSchema.model_json_schema(),
        )
        if not raw_out:
            return None
        parsed = _GeminiFaceCompareSchema.model_validate_json(raw_out)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Gemini face comparison failed: %s", exc.__class__.__name__)
        return None

    return GeminiFaceCompareResult(
        selfie_has_clear_face=parsed.selfie_has_clear_face,
        aadhaar_face_detected=parsed.aadhaar_face_detected,
        aadhaar_match_score=(round(float(parsed.aadhaar_match_score), 3) if parsed.aadhaar_match_score is not None else None),
        pan_face_detected=parsed.pan_face_detected,
        pan_match_score=(round(float(parsed.pan_match_score), 3) if parsed.pan_match_score is not None else None),
        overall_match_score=(round(float(parsed.overall_match_score), 3) if parsed.overall_match_score is not None else None),
        verdict=parsed.verdict,
        reasoning=_mask_sensitive_text(parsed.reasoning),
    )


def enhance_ocr_result_with_gemini_vision(
    *,
    doc_type: str,
    content_type: str,
    raw_bytes: bytes,
    res: object,
    cfg: EffectiveIntegrationsConfig,
) -> object:
    """Upgrade an OcrPipelineResult using Gemini multimodal vision when GEMINI_API_KEY is available."""
    from dataclasses import replace

    from app.services.ocr_pipeline import (
        EXPECTED_FIELDS_BY_DOC,
        PAN_STRICT_RE,
        _normalize_ifsc_ocr,
        _normalize_pan_ocr,
        extract_fields_for_doc,
        mask_aadhaar_numbers_in_text,
        normalize_date_str,
        normalize_person_name,
    )

    if not cfg.gemini_api_key:
        return res

    should_run = (
        cfg.ai_provider == "gemini"
        or getattr(res, "ocr_engine", "") == "OCR_UNAVAILABLE"
        or not (getattr(res, "raw_ocr_text_masked", "") or "").strip()
        or bool(getattr(res, "missing_fields", []))
    )
    if not should_run:
        return res

    g_res = extract_document_with_gemini_vision(
        expected_doc_type=doc_type,
        content_type=content_type,
        raw_bytes=raw_bytes,
        cfg=cfg,
    )
    if g_res is None:
        return res

    combined_raw_text = "\n".join(
        p for p in (getattr(res, "raw_ocr_text_masked", "") or "", g_res.raw_text_masked) if p.strip()
    ).strip()
    masked_text, aadhaar_hits = mask_aadhaar_numbers_in_text(combined_raw_text)

    # Re-run deterministic regex extraction over the richer masked text as baseline
    regex_fields, _ = extract_fields_for_doc(
        doc_type,
        masked_text,
        face_detected=g_res.face_detected if g_res.face_detected is not None else res.quality.face_detected,
    )
    merged_fields: dict[str, str] = dict(res.extracted_fields or {})
    merged_fields.update(regex_fields)

    # Normalize & overlay structured Gemini fields safely
    for k, val in g_res.raw_fields.items():
        if not val:
            continue
        if k in ("full_name", "father_name"):
            norm = normalize_person_name(val)
            if norm and len(norm.replace(" ", "")) >= 3:
                merged_fields[k] = norm
        elif k == "dob":
            norm_dt = normalize_date_str(val) or (val.strip() if re.fullmatch(r"(19\d{2}|20[0-2]\d)", val.strip()) else None)
            if norm_dt:
                merged_fields["dob"] = norm_dt
        elif k == "pan_number":
            pan = _normalize_pan_ocr(val)
            if PAN_STRICT_RE.match(pan):
                merged_fields["pan_number"] = pan
        elif k == "ifsc_code":
            ifsc = _normalize_ifsc_ocr(val)
            if re.fullmatch(r"^[A-Z]{4}0[A-Z0-9]{6}$", ifsc):
                merged_fields["ifsc_code"] = ifsc
        elif k == "pincode":
            pin = re.sub(r"\D", "", val)
            if len(pin) == 6:
                merged_fields["pincode"] = pin
        elif k == "gender":
            up_g = val.strip().upper()
            if up_g in ("MALE", "FEMALE", "OTHER"):
                merged_fields["gender"] = up_g
        elif k == "result_status":
            up_r = val.strip().upper()
            if "PASS" in up_r:
                merged_fields["result_status"] = "PASS"
            elif "FAIL" in up_r:
                merged_fields["result_status"] = "FAIL"
        elif k == "passing_year":
            yr = re.search(r"(19\d{2}|20[0-3]\d)", val)
            if yr:
                merged_fields["passing_year"] = yr.group(1)
        elif k == "aadhaar_last4":
            if re.fullmatch(r"\d{4}", val):
                merged_fields["aadhaar_last4"] = val
        elif k == "account_last4":
            if re.fullmatch(r"\d{4}", val):
                merged_fields["account_last4"] = val
        else:
            merged_fields[k] = val

    # Filter out 1-2 character regex noise in person names
    for name_key in ("full_name", "father_name"):
        if name_key in merged_fields and len(merged_fields[name_key].replace(" ", "")) < 3:
            merged_fields.pop(name_key, None)

    if doc_type == "AADHAAR_BACK" and ("pincode" in merged_fields or g_res.raw_fields.get("address_or_pincode")):
        merged_fields["address_or_pincode"] = merged_fields.get("pincode") or g_res.raw_fields.get("address_or_pincode", "")

    face_det = res.quality.face_detected
    if doc_type == "APPLICANT_SELFIE":
        if g_res.face_detected is not None:
            face_det = bool(face_det or g_res.face_detected)
        if face_det is not None:
            merged_fields["face_detected"] = "true" if face_det else "false"

    expected = EXPECTED_FIELDS_BY_DOC.get(doc_type, [])
    missing = [f for f in expected if not merged_fields.get(f) or (f == "face_detected" and merged_fields[f] != "true")]

    # Quality refinement from multimodal visual inspection
    q_status = res.quality.quality_status
    if g_res.appears_blank_or_fake or not g_res.is_valid_document:
        if q_status == "OK":
            q_status = "UNREADABLE"
    elif q_status == "OK":
        if doc_type == "APPLICANT_SELFIE" and face_det is False:
            q_status = "FACE_NOT_DETECTED"
        elif g_res.is_blurry and g_res.ocr_confidence < 0.65:
            q_status = "IMAGE_BLURRY"
        elif g_res.has_heavy_glare and g_res.ocr_confidence < 0.65:
            q_status = "IMAGE_GLARE"
        elif g_res.is_cropped and missing:
            q_status = "IMAGE_CROPPED"

    updated_quality = replace(res.quality, quality_status=q_status, face_detected=face_det)

    # Classification refinement
    pred_type = res.predicted_doc_type
    pred_conf = res.classification_confidence
    pred_match = res.classification_match
    if g_res.predicted_doc_type != "UNKNOWN" and (
        pred_type == "UNKNOWN" or g_res.classification_confidence >= (pred_conf or 0.0)
    ):
        pred_type = g_res.predicted_doc_type
        pred_conf = g_res.classification_confidence
        pred_match = pred_type == doc_type

    base_engine = getattr(res, "ocr_engine", "OCR_UNAVAILABLE")
    new_engine = (
        "GEMINI_VISION"
        if base_engine in ("OCR_UNAVAILABLE", "LOCAL_TESSERACT") and not (getattr(res, "raw_ocr_text_masked", "") or "").strip()
        else f"{base_engine}+GEMINI_VISION"
    )
    ocr_conf = max(float(getattr(res, "ocr_confidence", None) or 0.0), g_res.ocr_confidence)

    return replace(
        res,
        ocr_engine=new_engine,
        quality=updated_quality,
        predicted_doc_type=pred_type,
        classification_confidence=pred_conf,
        classification_match=pred_match,
        ocr_confidence=round(ocr_conf, 3),
        raw_ocr_text_masked=masked_text,
        extracted_fields=merged_fields,
        missing_fields=missing,
        aadhaar_masked_applied=bool(getattr(res, "aadhaar_masked_applied", False) or bool(aadhaar_hits)),
    )
