"""Phase 4 deterministic policy rules engine, decision management, rework, appeals, and reapplications."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import Request
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.deps import AuthContext
from app.core.errors import AppError
from app.models import (
    Application,
    ApplicationAppeal,
    ApplicationDecision,
    ApplicationDocument,
    ApplicationEvent,
    DocumentExtraction,
    RuleExecution,
    RuleSet,
    VerificationCheck,
)
from app.models.application import ACTIVE_APPLICATION_STATUSES, REQUIRED_DOC_TYPES
from app.models.base import utcnow
from app.schemas.rules import (
    AppealCreateRequest,
    AppealResolveRequest,
    ApplicationAppealOut,
    ApplicationDecisionOut,
    ApplicationDecisionSummaryOut,
    ReapplyRequest,
    ReviewerDecisionRequest,
    ReworkItemOut,
    RuleConfigSchema,
    RuleExecutionOut,
    RuleSetCreateRequest,
)
from app.services import audit
from app.services.applications import generate_reference_code, get_application
from app.services.consistency import IFSC_STRICT_RE, compare_dob_values, match_indian_names, validate_pan_format
from app.services.notifications import create_notification

HARD_STATUTORY_CODES = {
    "UNDERAGE",
    "PAN_FORMAT_INVALID",
    "PAN_NOT_INDIVIDUAL",
    "EDU_NOT_ELIGIBLE",
    "ALREADY_REGISTERED",
}

VALID_REASON_CODES = HARD_STATUTORY_CODES | {
    "IMAGE_BLURRY",
    "IMAGE_CROPPED",
    "IMAGE_GLARE",
    "NAME_MISMATCH",
    "NAME_SPELLING_VARIANT",
    "DOB_MISMATCH",
    "BANK_NAME_MISMATCH",
    "FACE_MATCH_LOW",
    "REVIEWER_DISCRETION",
}

# Bilingual consolidated rework templates per 04_CONSOLIDATED_REWORK_ENGINE.md
REWORK_TEMPLATES: dict[str, dict[str, str]] = {
    "IMAGE_BLURRY": {
        "title_en": "Document unclear or blurry",
        "title_hi": "दस्तावेज़ धुंधला या अस्पष्ट है",
        "action_en": "Re-upload a sharp, high-contrast photo in bright lighting with all text readable.",
        "action_hi": "अच्छी रोशनी में साफ और स्पष्ट फोटो दोबारा अपलोड करें ताकि सभी अक्षर पढ़े जा सकें।",
    },
    "IMAGE_GLARE": {
        "title_en": "Flash glare obscures details",
        "title_hi": "फ्लैश की चमक से जानकारी छिपी है",
        "action_en": "Turn off camera flash and tilt slightly to avoid light reflection on laminated plastic.",
        "action_hi": "कैमरा फ्लैश बंद करें और बिना चमक के दोबारा फोटो अपलोड करें।",
    },
    "IMAGE_CROPPED": {
        "title_en": "Document incomplete or corners cropped",
        "title_hi": "दस्तावेज़ अधूरा या कोने कटे हुए हैं",
        "action_en": "Ensure all four corners and required details of the document are fully visible.",
        "action_hi": "सुनिश्चित करें कि दस्तावेज़ के चारों कोने और सभी विवरण पूरी तरह दिखाई दें।",
    },
    "NAME_SPELLING_VARIANT": {
        "title_en": "Minor name spelling difference",
        "title_hi": "नाम की वर्तनी में हल्का अंतर है",
        "action_en": "Check your entered name against your PAN card or upload a clearer copy showing matching spelling.",
        "action_hi": "पैन कार्ड के अनुसार अपने नाम की वर्तनी जांचें या स्पष्ट दस्तावेज़ अपलोड करें।",
    },
    "DOB_MISMATCH": {
        "title_en": "Date of birth does not match PAN",
        "title_hi": "जन्म तिथि पैन कार्ड से मेल नहीं खाती",
        "action_en": "Correct your Date of Birth or upload a document whose DOB matches your PAN record.",
        "action_hi": "अपनी जन्म तिथि सही करें या पैन कार्ड से मेल खाने वाला दस्तावेज़ अपलोड करें।",
    },
    "BANK_NAME_MISMATCH": {
        "title_en": "Bank proof or IFSC incomplete",
        "title_hi": "बैंक विवरण या IFSC अधूरा है",
        "action_en": "Upload a clear cancelled cheque or passbook with IFSC and verify you are the primary account holder.",
        "action_hi": "IFSC सहित स्पष्ट रद्द चेक अपलोड करें और सुनिश्चित करें कि आप मुख्य खाताधारक हैं।",
    },
    "FACE_MATCH_LOW": {
        "title_en": "Selfie clarity or face check failed",
        "title_hi": "सेल्फी स्पष्ट नहीं है या चेहरा सत्यापित नहीं हुआ",
        "action_en": "Capture a bright, front-facing selfie without glasses or masks and upload again.",
        "action_hi": "बिना चश्मे या मास्क के साफ रोशनी में सीधी सेल्फी दोबारा अपलोड करें।",
    },
    "REVIEWER_DISCRETION": {
        "title_en": "Document type or information needs correction",
        "title_hi": "दस्तावेज़ प्रकार या जानकारी में सुधार आवश्यक है",
        "action_en": "Review the flagged section and upload the exact required document.",
        "action_hi": "चिह्नित अनुभाग की जांच करें और सही दस्तावेज़ अपलोड करें।",
    },
}

BOARD_ALIASES = {
    "CENTRAL BOARD OF SECONDARY EDUCATION": "CBSE",
    "COUNCIL FOR THE INDIAN SCHOOL CERTIFICATE": "CISCE",
    "NATIONAL INSTITUTE OF OPEN SCHOOLING": "NIOS",
}


def _mask_pan_for_evidence(pan: str | None) -> str | None:
    if not pan or len(pan) < 4:
        return None
    cleaned = pan.strip().upper()
    return f"{cleaned[:2]}***{cleaned[-2:]}"


def ensure_default_ruleset(db: Session) -> RuleSet:
    active = db.scalar(select(RuleSet).where(RuleSet.is_active.is_(True)))
    if active is not None:
        return active

    baseline = db.scalar(select(RuleSet).where(RuleSet.version == "3.2.0"))
    if baseline is not None:
        baseline.is_active = True
        baseline.status = "ACTIVE"
        baseline.activated_at = utcnow()
        db.flush()
        return baseline

    baseline = RuleSet(
        version="3.2.0",
        name="PS-01 POSP Onboarding Rulebook v3.2.0",
        description="Approved deterministic onboarding ruleset (eligibility, completeness, cross-doc consistency, risk).",
        status="ACTIVE",
        is_active=True,
        rules_config=RuleConfigSchema().model_dump(),
        activated_at=utcnow(),
    )
    db.add(baseline)
    db.flush()
    return baseline


def get_active_ruleset(db: Session) -> RuleSet:
    return ensure_default_ruleset(db)


def list_rulesets(db: Session) -> list[RuleSet]:
    ensure_default_ruleset(db)
    return list(db.scalars(select(RuleSet).order_by(desc(RuleSet.is_active), desc(RuleSet.created_at))).all())


def create_ruleset_version(
    db: Session,
    body: RuleSetCreateRequest,
    auth: AuthContext,
    request: Request,
) -> RuleSet:
    ensure_default_ruleset(db)
    existing = db.scalar(select(RuleSet).where(RuleSet.version == body.version.strip()))
    if existing is not None:
        raise AppError(409, "RULESET_VERSION_EXISTS", f"RuleSet version '{body.version}' already exists.")

    now = utcnow()
    if body.activate_immediately:
        prev_active = db.scalars(select(RuleSet).where(RuleSet.is_active.is_(True))).all()
        for rs in prev_active:
            rs.is_active = False
            rs.status = "ARCHIVED"
        db.flush()

    rs = RuleSet(
        version=body.version.strip(),
        name=body.name.strip(),
        description=body.description.strip() if body.description else None,
        status="ACTIVE" if body.activate_immediately else "DRAFT",
        is_active=body.activate_immediately,
        rules_config=body.rules_config.model_dump(),
        created_by_user_id=auth.user.id,
        activated_by_user_id=auth.user.id if body.activate_immediately else None,
        activated_at=now if body.activate_immediately else None,
    )
    db.add(rs)
    db.flush()
    audit.add(
        db,
        request,
        "ruleset.created",
        actor=auth.user,
        resource_type="rule_set",
        resource_id=str(rs.id),
        details={"version": rs.version, "activated": rs.is_active},
    )
    db.flush()
    return rs


def activate_ruleset_version(
    db: Session,
    ruleset_id: uuid.UUID,
    auth: AuthContext,
    request: Request,
) -> RuleSet:
    target = db.get(RuleSet, ruleset_id)
    if target is None:
        raise AppError(404, "RULESET_NOT_FOUND", "RuleSet version not found.")

    if target.is_active:
        return target

    for prev in db.scalars(select(RuleSet).where(RuleSet.is_active.is_(True))).all():
        prev.is_active = False
        prev.status = "ARCHIVED"
    db.flush()

    target.is_active = True
    target.status = "ACTIVE"
    target.activated_by_user_id = auth.user.id
    target.activated_at = utcnow()
    audit.add(
        db,
        request,
        "ruleset.activated",
        actor=auth.user,
        resource_type="rule_set",
        resource_id=str(target.id),
        details={"version": target.version},
    )
    db.flush()
    return target


def _add_rework_item(
    rework_map: dict[tuple[str | None, str], dict[str, Any]],
    doc_type: str | None,
    reason_code: str,
    custom_en: str | None = None,
    custom_hi: str | None = None,
) -> None:
    key = (doc_type, reason_code)
    if key in rework_map:
        return
    tpl = REWORK_TEMPLATES.get(reason_code, REWORK_TEMPLATES["REVIEWER_DISCRETION"])
    rework_map[key] = {
        "doc_type": doc_type,
        "reason_code": reason_code,
        "title_en": tpl["title_en"],
        "title_hi": tpl["title_hi"],
        "action_en": custom_en or tpl["action_en"],
        "action_hi": custom_hi or tpl["action_hi"],
    }


def _is_recognized_board(board_name: str | None, recognized: list[str]) -> bool:
    if not board_name:
        return False
    norm = board_name.strip().upper()
    for alias, canonical in BOARD_ALIASES.items():
        if alias in norm:
            norm = f"{norm} {canonical}"
    return any(token.strip().upper() in norm for token in recognized if token.strip())


def evaluate_application(
    db: Session,
    app: Application,
    auth: AuthContext,
    request: Request,
    *,
    trigger_source: str = "MANUAL_EVALUATE",
    apply_transition: bool = True,
) -> RuleExecution:
    """Run all PS-01 deterministic rules against application state + extractions and persist execution."""
    ruleset = get_active_ruleset(db)
    cfg = RuleConfigSchema.model_validate(ruleset.rules_config or {})

    current_docs = list(
        db.scalars(
            select(ApplicationDocument).where(
                ApplicationDocument.application_id == app.id,
                ApplicationDocument.is_current.is_(True),
            )
        ).all()
    )
    docs_by_type = {doc.doc_type: doc for doc in current_docs}

    extractions = list(db.scalars(select(DocumentExtraction).where(DocumentExtraction.application_id == app.id)).all())
    ext_by_doc_id = {ext.document_id: ext for ext in extractions}
    ext_by_type: dict[str, DocumentExtraction] = {}
    effective_by_type: dict[str, dict[str, Any]] = {}
    for doc_type, doc in docs_by_type.items():
        ext = ext_by_doc_id.get(doc.id)
        if ext is not None:
            ext_by_type[doc_type] = ext
            effective_by_type[doc_type] = dict(ext.effective_fields or {})

    checks = list(db.scalars(select(VerificationCheck).where(VerificationCheck.application_id == app.id)).all())
    face_check = next((c for c in checks if c.check_type == "FACE_MATCH"), None)

    rules: list[dict[str, Any]] = []
    risks: list[dict[str, Any]] = []
    rework_map: dict[tuple[str | None, str], dict[str, Any]] = {}

    def add_rule(
        rule_id: str,
        category: str,
        name: str,
        status: str,
        severity: str,
        explanation: str,
        reason_code: str | None = None,
        evidence: dict[str, Any] | None = None,
    ) -> None:
        rules.append(
            {
                "rule_id": rule_id,
                "category": category,
                "name": name,
                "status": status,
                "severity": severity,
                "reason_code": reason_code,
                "explanation": explanation,
                "evidence": evidence or {},
            }
        )

    pan_fields = effective_by_type.get("PAN_CARD", {})
    aadhaar_fields = effective_by_type.get("AADHAAR_FRONT", {})
    aadhaar_back_fields = effective_by_type.get("AADHAAR_BACK", {})
    marksheet_fields = effective_by_type.get("CLASS_10_MARKSHEET", {})
    bank_fields = effective_by_type.get("BANK_DOCUMENT", {})
    selfie_fields = effective_by_type.get("APPLICANT_SELFIE", {})

    anchor_name = pan_fields.get("full_name") or app.full_name
    anchor_dob = pan_fields.get("dob") or (app.date_of_birth.isoformat() if app.date_of_birth else None)
    pan_effective = (pan_fields.get("pan_number") or app.pan_number or "").strip().upper() or None

    # ------------------------------------------------------------------
    # 1. STATUTORY & ELIGIBILITY GATES
    # ------------------------------------------------------------------
    elig_ok = True

    # Age >= 18
    age_years: int | None = None
    if anchor_dob and len(str(anchor_dob)) >= 10:
        from datetime import date

        try:
            dob_dt = date.fromisoformat(str(anchor_dob)[:10])
            ref_dt = app.created_at.date()
            age_years = ref_dt.year - dob_dt.year - ((ref_dt.month, ref_dt.day) < (dob_dt.month, dob_dt.day))
        except ValueError:
            age_years = None

    if age_years is None:
        add_rule(
            "ELIG_AGE_18",
            "ELIGIBILITY",
            "Minimum Age >= 18 Years",
            "HUMAN_REVIEW",
            "HUMAN_ONLY",
            "Full date of birth is unavailable or could not be parsed cleanly for statutory age check.",
            "DOB_MISMATCH",
        )
        elig_ok = False
    elif age_years < cfg.min_age_years:
        add_rule(
            "ELIG_AGE_18",
            "ELIGIBILITY",
            "Minimum Age >= 18 Years",
            "FAIL",
            "HARD_REJECT",
            f"Applicant age ({age_years} yrs) is below IRDAI minimum age of {cfg.min_age_years} years.",
            "UNDERAGE",
            {"age_years": age_years, "min_age_years": cfg.min_age_years},
        )
        elig_ok = False
    else:
        add_rule(
            "ELIG_AGE_18",
            "ELIGIBILITY",
            "Minimum Age >= 18 Years",
            "PASS",
            "NONE",
            f"Applicant meets statutory minimum age ({age_years} >= {cfg.min_age_years}).",
            evidence={"age_years": age_years},
        )

    # Individual PAN check (format + 4th char == 'P')
    pan_outcome = validate_pan_format(pan_effective)
    pan_code = pan_outcome.details.get("reason_code")
    if pan_outcome.status == "FAILED":
        add_rule(
            "ELIG_PAN_VALID",
            "ELIGIBILITY",
            "Valid Individual PAN ('P')",
            "FAIL",
            "HARD_REJECT",
            pan_outcome.explanation,
            pan_code or "PAN_FORMAT_INVALID",
            {
                "pan_masked": _mask_pan_for_evidence(pan_effective),
                "holder_type": pan_outcome.details.get("holder_type"),
            },
        )
        elig_ok = False
    elif pan_outcome.status == "PASSED":
        add_rule(
            "ELIG_PAN_VALID",
            "ELIGIBILITY",
            "Valid Individual PAN ('P')",
            "PASS",
            "NONE",
            pan_outcome.explanation,
            evidence={"pan_masked": _mask_pan_for_evidence(pan_effective), "holder_type": "P"},
        )
    else:
        add_rule(
            "ELIG_PAN_VALID",
            "ELIGIBILITY",
            "Valid Individual PAN ('P')",
            "FAIL",
            "REWORK",
            "PAN number could not be read from card or application.",
            "IMAGE_BLURRY",
        )
        _add_rework_item(rework_map, "PAN_CARD", "IMAGE_BLURRY")
        elig_ok = False

    # Education >= Class 10 Pass & Recognized Board
    edu_result = str(marksheet_fields.get("result_status") or app.result_status or "").strip().upper()
    edu_level = str(app.education_level or "").strip().upper()
    board_name = marksheet_fields.get("board_name") or app.board_name
    if edu_level in ("BELOW_10TH", "NONE") or edu_result in ("FAIL", "FAILED", "COMPARTMENT"):
        add_rule(
            "ELIG_EDU_CLASS10",
            "ELIGIBILITY",
            "Minimum Class 10 Pass Qualification",
            "FAIL",
            "HARD_REJECT",
            "Applicant does not meet minimum Class 10 PASS qualification required by IRDAI POSP guidelines.",
            "EDU_NOT_ELIGIBLE",
            {"education_level": edu_level, "result_status": edu_result or None},
        )
        elig_ok = False
    elif board_name and not _is_recognized_board(str(board_name), cfg.recognized_education_boards):
        add_rule(
            "ELIG_EDU_CLASS10",
            "ELIGIBILITY",
            "Minimum Class 10 Pass Qualification",
            "HUMAN_REVIEW",
            "HUMAN_ONLY",
            f"Education board '{board_name}' is not in the recognized auto-pass list; manual verification required.",
            "REVIEWER_DISCRETION",
            {"board_name": str(board_name)},
        )
    else:
        add_rule(
            "ELIG_EDU_CLASS10",
            "ELIGIBILITY",
            "Minimum Class 10 Pass Qualification",
            "PASS",
            "NONE",
            "Class 10+ qualification and recognized board verified.",
            evidence={"education_level": edu_level, "board_name": str(board_name or "")},
        )

    # POSP Exclusivity & Duplicate Active PAN check
    dup_pan_app = None
    if pan_effective:
        dup_pan_app = db.scalar(
            select(Application).where(
                Application.id != app.id,
                Application.pan_number == pan_effective,
                Application.status.in_(("KYC_APPROVED", "TRAINING_IN_PROGRESS", "CERTIFIED")),
            )
        )
    if (app.submitted_at and not app.declaration_no_other_posp) or dup_pan_app is not None:
        why = (
            "Another approved or certified POSP onboarding application already exists for this PAN."
            if dup_pan_app is not None
            else "Applicant did not affirm IRDAI exclusivity (no active engagement with another insurer/intermediary)."
        )
        add_rule(
            "ELIG_POSP_EXCLUSIVITY",
            "ELIGIBILITY",
            "IRDAI Single-Intermediary Exclusivity",
            "FAIL",
            "HARD_REJECT",
            why,
            "ALREADY_REGISTERED",
            {"existing_application_ref": dup_pan_app.reference_code if dup_pan_app else None},
        )
        elig_ok = False
    else:
        add_rule(
            "ELIG_POSP_EXCLUSIVITY",
            "ELIGIBILITY",
            "IRDAI Single-Intermediary Exclusivity",
            "PASS",
            "NONE",
            "No conflicting active/certified POSP PAN record found and exclusivity affirmed.",
        )

    # ------------------------------------------------------------------
    # 2. COMPLETENESS & DOCUMENT QUALITY GATES
    # ------------------------------------------------------------------
    comp_ok = True
    missing_docs = [dt for dt in REQUIRED_DOC_TYPES if dt not in docs_by_type]
    if cfg.require_all_six_documents and missing_docs:
        add_rule(
            "DOC_ALL_SIX_PRESENT",
            "COMPLETENESS",
            "All 6 Mandatory KYC Documents Uploaded",
            "FAIL",
            "REWORK",
            f"Missing mandatory documents: {', '.join(missing_docs)}.",
            "IMAGE_CROPPED",
            {"missing_documents": missing_docs},
        )
        for mdoc in missing_docs:
            _add_rework_item(
                rework_map,
                mdoc,
                "IMAGE_CROPPED",
                custom_en=f"Please upload your missing {mdoc.replace('_', ' ').title()} document.",
                custom_hi=f"कृपया अपना {mdoc.replace('_', ' ')} दस्तावेज़ अपलोड करें।",
            )
        comp_ok = False
    else:
        add_rule(
            "DOC_ALL_SIX_PRESENT",
            "COMPLETENESS",
            "All 6 Mandatory KYC Documents Uploaded",
            "PASS",
            "NONE",
            "All 6 mandatory KYC documents are present.",
        )

    quality_issues: list[str] = []
    for doc_type, _doc in docs_by_type.items():
        ext = ext_by_type.get(doc_type)
        if ext is None:
            quality_issues.append(f"{doc_type}: not yet processed")
            _add_rework_item(rework_map, doc_type, "REVIEWER_DISCRETION")
            continue

        if ext.classification_match is False:
            quality_issues.append(f"{doc_type}: classified as {ext.predicted_doc_type}")
            _add_rework_item(
                rework_map,
                doc_type,
                "REVIEWER_DISCRETION",
                custom_en=f"Uploaded file appears to be {ext.predicted_doc_type} instead of {doc_type}. Please upload the correct document.",
            )

        if ext.quality_status in (
            "UNREADABLE",
            "LOW_RESOLUTION",
            "IMAGE_BLURRY",
            "IMAGE_GLARE",
            "IMAGE_CROPPED",
            "FACE_NOT_DETECTED",
        ):
            rc = {
                "UNREADABLE": "IMAGE_BLURRY",
                "LOW_RESOLUTION": "IMAGE_BLURRY",
                "IMAGE_BLURRY": "IMAGE_BLURRY",
                "IMAGE_GLARE": "IMAGE_GLARE",
                "IMAGE_CROPPED": "IMAGE_CROPPED",
                "FACE_NOT_DETECTED": "FACE_MATCH_LOW",
            }[ext.quality_status]
            quality_issues.append(f"{doc_type}: quality {ext.quality_status}")
            _add_rework_item(rework_map, doc_type, rc)
        elif (
            doc_type != "APPLICANT_SELFIE"
            and ext.ocr_confidence is not None
            and ext.ocr_confidence < cfg.min_ocr_confidence
            and not ext.reviewer_corrected_fields
        ):
            if ext.missing_fields:
                quality_issues.append(f"{doc_type}: low OCR confidence ({ext.ocr_confidence:.2f})")
                _add_rework_item(rework_map, doc_type, "IMAGE_BLURRY")
            else:
                add_rule(
                    f"DOC_OCR_CONF_{doc_type}",
                    "COMPLETENESS",
                    f"OCR Confidence Threshold ({doc_type})",
                    "HUMAN_REVIEW",
                    "HUMAN_ONLY",
                    f"{doc_type} OCR confidence {ext.ocr_confidence:.2f} is below auto-pass floor {cfg.min_ocr_confidence:.2f}; human review required.",
                    "IMAGE_BLURRY",
                    {"doc_type": doc_type, "ocr_confidence": ext.ocr_confidence},
                )

    if quality_issues:
        add_rule(
            "DOC_QUALITY_AND_OCR",
            "COMPLETENESS",
            "Document Image Quality & Classification",
            "FAIL",
            "REWORK",
            "; ".join(quality_issues),
            "IMAGE_BLURRY",
            {"issues": quality_issues},
        )
        comp_ok = False
    else:
        add_rule(
            "DOC_QUALITY_AND_OCR",
            "COMPLETENESS",
            "Document Image Quality & Classification",
            "PASS",
            "NONE",
            "All uploaded documents passed local quality, classification, and OCR legibility checks.",
        )

    # ------------------------------------------------------------------
    # 3. CROSS-DOCUMENT IDENTITY & BANK CONSISTENCY
    # ------------------------------------------------------------------
    cons_ok = True

    # Declared PAN vs OCR PAN
    if (
        app.pan_number
        and pan_fields.get("pan_number")
        and app.pan_number.upper() != str(pan_fields["pan_number"]).upper()
    ):
        add_rule(
            "CONSIST_PAN_MATCH",
            "CONSISTENCY",
            "Declared PAN vs Card PAN",
            "HUMAN_REVIEW",
            "HUMAN_ONLY",
            "Declared PAN in profile does not match extracted PAN on card; reviewer confirmation required.",
            "REVIEWER_DISCRETION",
            {
                "declared_masked": _mask_pan_for_evidence(app.pan_number),
                "extracted_masked": _mask_pan_for_evidence(str(pan_fields["pan_number"])),
            },
        )
        cons_ok = False
    else:
        add_rule(
            "CONSIST_PAN_MATCH",
            "CONSISTENCY",
            "Declared PAN vs Card PAN",
            "PASS",
            "NONE",
            "Declared PAN matches PAN card extraction.",
        )

    # Name consistency (with strict safety invariant: NAME_MISMATCH NEVER auto-rejects!)
    name_targets = [
        ("PROFILE", app.full_name),
        ("AADHAAR_FRONT", aadhaar_fields.get("full_name")),
        ("CLASS_10_MARKSHEET", marksheet_fields.get("full_name")),
    ]
    for source_label, candidate_name in name_targets:
        if not anchor_name or not candidate_name:
            continue
        if source_label == "PROFILE" and anchor_name == app.full_name and not pan_fields.get("full_name"):
            continue
        nm = match_indian_names(str(anchor_name), str(candidate_name))
        if nm.verdict == "MATCH":
            add_rule(
                f"CONSIST_NAME_{source_label}",
                "CONSISTENCY",
                f"8-Tier Name Match ({source_label})",
                "PASS",
                "NONE",
                nm.explanation,
                evidence={"tier": nm.tier, "category": nm.category, "confidence": nm.confidence},
            )
        elif nm.reason_code == "NAME_MISMATCH" or nm.tier == 7:
            # SAFETY INVARIANT: Name mismatch requiring human confirmation MUST NEVER auto-reject
            add_rule(
                f"CONSIST_NAME_{source_label}",
                "CONSISTENCY",
                f"8-Tier Name Match ({source_label})",
                "HUMAN_REVIEW",
                "HUMAN_ONLY",
                f"{nm.explanation} Strictly routed to human confirmation (auto-rejection prohibited).",
                "NAME_MISMATCH",
                {
                    "tier": nm.tier,
                    "category": nm.category,
                    "confidence": nm.confidence,
                    "non_auto_reject_guardrail": True,
                },
            )
            cons_ok = False
        elif nm.reason_code == "NAME_SPELLING_VARIANT":
            add_rule(
                f"CONSIST_NAME_{source_label}",
                "CONSISTENCY",
                f"8-Tier Name Match ({source_label})",
                "FAIL",
                "REWORK",
                nm.explanation,
                "NAME_SPELLING_VARIANT",
                {"tier": nm.tier, "category": nm.category, "confidence": nm.confidence},
            )
            _add_rework_item(rework_map, None if source_label == "PROFILE" else source_label, "NAME_SPELLING_VARIANT")
            cons_ok = False
        else:
            # Tier 6 marriage surname change or discretionary
            add_rule(
                f"CONSIST_NAME_{source_label}",
                "CONSISTENCY",
                f"8-Tier Name Match ({source_label})",
                "HUMAN_REVIEW",
                "HUMAN_ONLY",
                nm.explanation,
                nm.reason_code or "REVIEWER_DISCRETION",
                {"tier": nm.tier, "category": nm.category, "confidence": nm.confidence},
            )
            cons_ok = False

    # DOB consistency across PAN, Aadhaar Front, Class 10
    for source_label, cand_dob in (
        ("PROFILE", app.date_of_birth.isoformat() if app.date_of_birth else None),
        ("AADHAAR_FRONT", aadhaar_fields.get("dob")),
        ("CLASS_10_MARKSHEET", marksheet_fields.get("dob")),
    ):
        if not anchor_dob or not cand_dob:
            continue
        dob_res = compare_dob_values(str(anchor_dob), str(cand_dob), source_label)
        if dob_res.status == "PASSED":
            add_rule(
                f"CONSIST_DOB_{source_label}",
                "CONSISTENCY",
                f"DOB Match ({source_label})",
                "PASS",
                "NONE",
                dob_res.explanation,
            )
        elif dob_res.status == "NEEDS_INFO":
            add_rule(
                f"CONSIST_DOB_{source_label}",
                "CONSISTENCY",
                f"DOB Match ({source_label})",
                "FAIL",
                "REWORK",
                dob_res.explanation,
                "DOB_MISMATCH",
            )
            _add_rework_item(rework_map, None if source_label == "PROFILE" else source_label, "DOB_MISMATCH")
            cons_ok = False

    # Bank format, joint holder, and account holder name
    ifsc_val = str(bank_fields.get("ifsc_code") or app.ifsc_code or "").strip().upper()
    holder_val = bank_fields.get("full_name") or app.account_holder_name
    bank_issues: list[str] = []
    if not ifsc_val or not IFSC_STRICT_RE.match(ifsc_val):
        bank_issues.append("Valid 11-character IFSC missing or invalid.")
    if app.is_joint_account and not app.is_primary_holder:
        bank_issues.append("Joint bank account requires applicant to be primary holder.")

    if bank_issues:
        add_rule(
            "CONSIST_BANK_DETAILS",
            "CONSISTENCY",
            "Bank IFSC & Account Ownership",
            "FAIL",
            "REWORK",
            " ".join(bank_issues),
            "BANK_NAME_MISMATCH",
        )
        _add_rework_item(rework_map, "BANK_DOCUMENT", "BANK_NAME_MISMATCH")
        cons_ok = False
    elif anchor_name and holder_val:
        nm_bank = match_indian_names(
            str(anchor_name), str(holder_val), allow_bank_truncation=cfg.allow_bank_truncation_match
        )
        if nm_bank.verdict == "MATCH":
            add_rule(
                "CONSIST_BANK_DETAILS",
                "CONSISTENCY",
                "Bank IFSC & Account Holder Name",
                "PASS",
                "NONE",
                f"Valid IFSC ({ifsc_val}) and {nm_bank.explanation}",
                evidence={"tier": nm_bank.tier, "category": nm_bank.category},
            )
        elif nm_bank.reason_code == "NAME_MISMATCH" or nm_bank.tier == 7:
            add_rule(
                "CONSIST_BANK_DETAILS",
                "CONSISTENCY",
                "Bank Account Holder Name",
                "HUMAN_REVIEW",
                "HUMAN_ONLY",
                f"{nm_bank.explanation} Bank name divergence requires human review (never auto-rejected).",
                "NAME_MISMATCH",
                {"tier": nm_bank.tier, "non_auto_reject_guardrail": True},
            )
            cons_ok = False
        else:
            add_rule(
                "CONSIST_BANK_DETAILS",
                "CONSISTENCY",
                "Bank Account Holder Name",
                "FAIL",
                "REWORK",
                nm_bank.explanation,
                "BANK_NAME_MISMATCH",
            )
            _add_rework_item(rework_map, "BANK_DOCUMENT", "BANK_NAME_MISMATCH")
            cons_ok = False
    else:
        add_rule(
            "CONSIST_BANK_DETAILS",
            "CONSISTENCY",
            "Bank IFSC Validation",
            "PASS",
            "NONE",
            f"IFSC ({ifsc_val}) matches RBI format.",
        )

    # ------------------------------------------------------------------
    # 4. BIOMETRIC & SELFIE CHECK
    # ------------------------------------------------------------------
    selfie_ext = ext_by_type.get("APPLICANT_SELFIE")
    face_detected: bool | None = None
    if selfie_ext is not None:
        raw_face = (selfie_ext.effective_fields or {}).get("face_detected")
        face_detected = (str(raw_face).lower() == "true") if raw_face is not None else selfie_ext.face_detected

    raw_face_score = selfie_fields.get("face_score") or (face_check.details.get("score") if face_check else None)
    face_score: float | None = None
    if raw_face_score is not None:
        try:
            face_score = float(raw_face_score)
        except (TypeError, ValueError):
            face_score = None

    if "APPLICANT_SELFIE" in docs_by_type:
        if face_detected is False:
            add_rule(
                "EXT_BIOMETRIC_FACE_MATCH",
                "BIOMETRIC",
                "Selfie Face Detection & Biometric Match",
                "FAIL",
                "REWORK",
                "No clear frontal face was detected in the applicant selfie.",
                "FACE_MATCH_LOW",
            )
            _add_rework_item(rework_map, "APPLICANT_SELFIE", "FACE_MATCH_LOW")
            cons_ok = False
        elif face_score is not None:
            if face_score < cfg.face_match_rework_threshold:
                add_rule(
                    "EXT_BIOMETRIC_FACE_MATCH",
                    "BIOMETRIC",
                    "Biometric Face Match Score",
                    "FAIL",
                    "REWORK",
                    f"Biometric face similarity score ({face_score:.2f}) is below minimum threshold ({cfg.face_match_rework_threshold:.2f}).",
                    "FACE_MATCH_LOW",
                    {"face_score": face_score},
                )
                _add_rework_item(rework_map, "APPLICANT_SELFIE", "FACE_MATCH_LOW")
                cons_ok = False
            elif face_score < cfg.face_match_auto_pass_threshold:
                add_rule(
                    "EXT_BIOMETRIC_FACE_MATCH",
                    "BIOMETRIC",
                    "Biometric Face Match Score",
                    "HUMAN_REVIEW",
                    "HUMAN_ONLY",
                    f"Biometric score ({face_score:.2f}) falls in manual confirmation band ({cfg.face_match_rework_threshold:.2f}-{cfg.face_match_auto_pass_threshold:.2f}).",
                    "REVIEWER_DISCRETION",
                    {"face_score": face_score},
                )
                cons_ok = False
            else:
                add_rule(
                    "EXT_BIOMETRIC_FACE_MATCH",
                    "BIOMETRIC",
                    "Biometric Face Match Score",
                    "PASS",
                    "NONE",
                    f"Biometric face match passed ({face_score:.2f} >= {cfg.face_match_auto_pass_threshold:.2f}).",
                    evidence={"face_score": face_score},
                )
        else:
            add_rule(
                "EXT_BIOMETRIC_FACE_MATCH",
                "BIOMETRIC",
                "Biometric Face Match Provider Boundary",
                "NOT_EVALUATED",
                "INFO",
                "Local selfie face detection passed, but external biometric comparison provider is not configured (no fabricated score).",
            )

    # ------------------------------------------------------------------
    # 5. RISK INDICATORS (PS-01 Section 4.2 & 4.3)
    # ------------------------------------------------------------------
    # PAN 5th char vs last name first char (informational only)
    if pan_effective and len(pan_effective) >= 5 and anchor_name:
        tokens = str(anchor_name).strip().upper().split()
        if tokens and pan_effective[4] != tokens[-1][0]:
            msg = (
                f"PAN 5th character ('{pan_effective[4]}') differs from surname initial ('{tokens[-1][0]}'). "
                "Informational indicator only (may reflect father/husband name or middle-name order); never rejects alone."
            )
            risks.append({"code": "PAN_5TH_CHAR_SURNAME", "level": "LOW", "message": msg})
            add_rule("RISK_PAN_5TH_CHAR_SURNAME", "RISK", "PAN 5th Character Surname Check", "INFO", "INFO", msg)

    # Aadhaar state vs residential state difference (informational only per PS-01)
    aadhaar_state = str(aadhaar_back_fields.get("state") or app.permanent_state or "").strip().upper()
    res_state = str(app.state or "").strip().upper()
    if aadhaar_state and res_state and aadhaar_state != res_state:
        msg = (
            f"Permanent/Aadhaar state ('{aadhaar_state}') differs from current residential state ('{res_state}'). "
            "Informational indicator only — never grounds for rejection."
        )
        risks.append({"code": "STATE_DIFFERENCE", "level": "INFO", "message": msg})
        add_rule("RISK_STATE_MISMATCH", "RISK", "Current vs Permanent State Check", "INFO", "INFO", msg)

    # Repeated rework escalation (>= 2 previous rework cycles)
    if app.rework_count >= cfg.max_rework_cycles_before_human:
        msg = (
            f"Application has completed {app.rework_count} rework cycles "
            f"(limit: {cfg.max_rework_cycles_before_human}). Escalated for Fraud/Operations manual inspection."
        )
        risks.append({"code": "REPEATED_REWORK_ESCALATION", "level": "HIGH", "message": msg})
        add_rule(
            "RISK_REPEATED_REWORK",
            "RISK",
            "Repeated Rework Threshold",
            "HUMAN_REVIEW",
            "HUMAN_ONLY",
            msg,
            "REVIEWER_DISCRETION",
            {"rework_count": app.rework_count, "threshold": cfg.max_rework_cycles_before_human},
        )

    # Unconfigured external verification provider disclosure
    unconfigured_providers = [c.check_type for c in checks if c.status == "NOT_CONFIGURED"]
    if unconfigured_providers:
        risks.append(
            {
                "code": "EXTERNAL_PROVIDERS_UNCONFIGURED",
                "level": "INFO",
                "message": f"External verification adapters unconfigured: {', '.join(sorted(set(unconfigured_providers)))}.",
            }
        )

    # ------------------------------------------------------------------
    # CONFLICT RESOLUTION & DETERMINISTIC DECISION ROUTING
    # ------------------------------------------------------------------
    hard_reject_rules = [r for r in rules if r["status"] == "FAIL" and r["severity"] == "HARD_REJECT"]
    human_only_rules = [r for r in rules if r["status"] == "HUMAN_REVIEW" or r["severity"] == "HUMAN_ONLY"]
    rework_rules = [r for r in rules if r["status"] == "FAIL" and r["severity"] == "REWORK"]

    reason_codes: list[str] = []
    for r in hard_reject_rules + human_only_rules + rework_rules:
        rc = r.get("reason_code")
        if rc and rc not in reason_codes:
            reason_codes.append(rc)

    auto_pass_eligible = False
    requires_human_review = False

    if hard_reject_rules:
        # Rejection Trumps Rework: suppress rework items on statutory disqualification
        outcome = "REJECT_RECOMMENDED"
        recommended_status = "REJECTED" if cfg.auto_reject_statutory else "IN_REVIEW"
        rework_items: list[dict[str, Any]] = []
        requires_human_review = not cfg.auto_reject_statutory
        summary = f"Statutory eligibility failed ({', '.join(r['reason_code'] or r['rule_id'] for r in hard_reject_rules)}). Rework suppressed."
    elif human_only_rules:
        outcome = "HUMAN_REVIEW"
        recommended_status = "IN_REVIEW"
        requires_human_review = True
        rework_items = list(rework_map.values())
        summary = f"Routed to mandatory human review ({', '.join(r['reason_code'] or r['rule_id'] for r in human_only_rules)})."
    elif rework_rules or rework_map:
        outcome = "NEEDS_MORE_INFO"
        recommended_status = "NEEDS_MORE_INFO"
        rework_items = list(rework_map.values())
        summary = f"Consolidated single-pass rework generated ({len(rework_items)} item(s))."
    elif not cfg.auto_approve_enabled:
        outcome = "HUMAN_REVIEW"
        recommended_status = "IN_REVIEW"
        auto_pass_eligible = True
        requires_human_review = True
        rework_items = []
        summary = "Eligible for pass, but active ruleset requires human reviewer sign-off."
    else:
        outcome = "AUTO_PASS_ELIGIBLE"
        recommended_status = "KYC_APPROVED"
        auto_pass_eligible = True
        rework_items = []
        summary = "All statutory eligibility, 6-document completeness, and consistency checks passed for KYC approval."

    risk_level = "HIGH" if any(r["level"] == "HIGH" for r in risks) else ("LOW" if risks else "LOW")
    if any(r["level"] == "MEDIUM" for r in risks):
        risk_level = "MEDIUM"

    execution = RuleExecution(
        application_id=app.id,
        ruleset_id=ruleset.id,
        ruleset_version=ruleset.version,
        trigger_source=trigger_source,
        triggered_by_user_id=auth.user.id,
        outcome=outcome,
        recommended_status=recommended_status,
        eligibility_status="PASS" if elig_ok else ("REJECT" if hard_reject_rules else "HUMAN_REVIEW"),
        completeness_status="PASS" if comp_ok else "FAIL",
        consistency_status="PASS" if cons_ok else ("HUMAN_REVIEW" if human_only_rules else "FAIL"),
        risk_level=risk_level,
        auto_pass_eligible=auto_pass_eligible,
        requires_human_review=requires_human_review,
        reason_codes=reason_codes,
        rule_results=rules,
        rework_items=rework_items,
        risk_indicators=risks,
        summary=summary,
    )
    db.add(execution)
    db.flush()

    prev_status = app.status
    if apply_transition and app.status in ("SUBMITTED", "REWORK_SUBMITTED", "IN_REVIEW"):
        app.status = recommended_status
        app.last_saved_at = utcnow()
        if recommended_status == "NEEDS_MORE_INFO":
            app.resolution_kind = "CORRECTION"
            create_notification(
                db,
                user_id=app.user_id,
                application_id=app.id,
                category="REWORK",
                title=f"Action required for {app.reference_code}",
                body="One or more documents/details need correction before approval. Review your rework checklist and resubmit.",
                action_url=f"/app/onboarding/{app.id}?step=5",
            )
        elif recommended_status == "KYC_APPROVED":
            app.resolution_kind = app.resolution_kind or "INITIAL"
            create_notification(
                db,
                user_id=app.user_id,
                application_id=app.id,
                category="APPLICATION",
                title=f"KYC approved for {app.reference_code}",
                body="All deterministic PolicyNest KYC checks passed.",
                action_url=f"/app/applications/{app.id}",
            )
        elif recommended_status == "REJECTED":
            app.resolution_kind = app.resolution_kind or "INITIAL"
            create_notification(
                db,
                user_id=app.user_id,
                application_id=app.id,
                category="APPLICATION",
                title=f"Application {app.reference_code} not eligible",
                body="Your application did not pass statutory POSP eligibility rules. Check the decision timeline for details or appeal/reapply.",
                action_url=f"/app/applications/{app.id}",
            )
        else:
            create_notification(
                db,
                user_id=app.user_id,
                application_id=app.id,
                category="APPLICATION",
                title=f"Application {app.reference_code} is in human review",
                body="A PolicyNest compliance reviewer is verifying flagged items on your application.",
                action_url=f"/app/applications/{app.id}",
            )

    db.add(
        ApplicationEvent(
            application_id=app.id,
            actor_user_id=auth.user.id,
            actor_role=auth.user.role.code,
            event_type="RULES_EVALUATED",
            from_status=prev_status,
            to_status=app.status,
            summary=f"Ruleset v{ruleset.version} evaluated ({outcome}): {summary}",
            details={
                "ruleset_version": ruleset.version,
                "outcome": outcome,
                "recommended_status": recommended_status,
                "reason_codes": reason_codes,
                "transition_applied": apply_transition and prev_status != app.status,
            },
        )
    )
    audit.add(
        db,
        request,
        "rules.evaluated",
        actor=auth.user,
        resource_type="application",
        resource_id=str(app.id),
        details={
            "reference_code": app.reference_code,
            "ruleset_version": ruleset.version,
            "outcome": outcome,
            "recommended_status": recommended_status,
            "reason_codes": reason_codes,
        },
    )
    db.flush()
    return execution


def record_reviewer_decision(
    db: Session,
    app: Application,
    body: ReviewerDecisionRequest,
    auth: AuthContext,
    request: Request,
) -> ApplicationDecision:
    if app.status in ("DRAFT", "WITHDRAWN"):
        raise AppError(
            409, "INVALID_STATUS_FOR_DECISION", "Cannot record a review decision on a draft or withdrawn application."
        )

    invalid_codes = [c for c in body.reason_codes if c not in VALID_REASON_CODES]
    if invalid_codes:
        raise AppError(422, "INVALID_REASON_CODE", f"Unsupported reason code(s): {', '.join(invalid_codes)}")

    latest_exec = db.scalar(
        select(RuleExecution)
        .where(RuleExecution.application_id == app.id)
        .order_by(desc(RuleExecution.executed_at))
        .limit(1)
    )

    latest_outcome = latest_exec.outcome if latest_exec else None
    latest_codes = set(latest_exec.reason_codes or []) if latest_exec else set()

    # Check if escalated senior permission is needed:
    # 1) Overriding a statutory rejection recommendation or reversing an already REJECTED app
    # 2) Approving/rejecting a Tier 7 NAME_MISMATCH human-only case
    is_statutory_override = latest_outcome == "REJECT_RECOMMENDED" and body.decision in ("APPROVE", "NEEDS_MORE_INFO")
    is_name_mismatch_case = "NAME_MISMATCH" in latest_codes and body.decision in ("APPROVE", "REJECT")
    is_reversal_from_rejected = app.status == "REJECTED" and body.decision != "ESCALATE"

    if (is_statutory_override or is_name_mismatch_case or is_reversal_from_rejected) and (
        "application:decide_escalated" not in auth.permissions
    ):
        raise AppError(
            403,
            "ESCALATED_DECISION_REQUIRED",
            "Overriding statutory eligibility, reversing a rejection, or deciding a NAME_MISMATCH case requires a Senior Reviewer (application:decide_escalated). Use ESCALATE instead.",
        )

    decision_to_status = {
        "APPROVE": "KYC_APPROVED",
        "NEEDS_MORE_INFO": "NEEDS_MORE_INFO",
        "REJECT": "REJECTED",
        "ESCALATE": "IN_REVIEW",
    }
    prev_status = app.status
    new_status = decision_to_status[body.decision]

    is_override = False
    if latest_exec is not None:
        if (latest_exec.recommended_status != new_status) and body.decision != "ESCALATE":
            is_override = True

    rework_payload = [item.model_dump() for item in body.rework_items]
    if body.decision == "NEEDS_MORE_INFO" and not rework_payload:
        for rc in body.reason_codes:
            tpl = REWORK_TEMPLATES.get(rc, REWORK_TEMPLATES["REVIEWER_DISCRETION"])
            rework_payload.append(
                ReworkItemOut(
                    doc_type=None,
                    reason_code=rc,
                    title_en=tpl["title_en"],
                    title_hi=tpl["title_hi"],
                    action_en=tpl["action_en"],
                    action_hi=tpl["action_hi"],
                ).model_dump()
            )

    decision_row = ApplicationDecision(
        application_id=app.id,
        rule_execution_id=latest_exec.id if latest_exec else None,
        decided_by_user_id=auth.user.id,
        decided_by_role=auth.user.role.code,
        decision=body.decision,
        previous_status=prev_status,
        new_status=new_status,
        is_override=is_override,
        override_of_outcome=latest_outcome if is_override else None,
        reason_codes=body.reason_codes,
        reason_text=body.reason_text.strip(),
        rework_items=rework_payload,
    )
    db.add(decision_row)

    app.status = new_status
    app.last_saved_at = utcnow()
    if new_status == "NEEDS_MORE_INFO":
        app.resolution_kind = "CORRECTION"

    event_type = f"REVIEWER_{body.decision}"
    db.add(
        ApplicationEvent(
            application_id=app.id,
            actor_user_id=auth.user.id,
            actor_role=auth.user.role.code,
            event_type=event_type,
            from_status=prev_status,
            to_status=new_status,
            summary=f"{auth.user.role.code} recorded decision {body.decision}{' (override)' if is_override else ''}.",
            details={
                "decision": body.decision,
                "is_override": is_override,
                "override_of_outcome": decision_row.override_of_outcome,
                "reason_codes": body.reason_codes,
                "reason_text": decision_row.reason_text,
            },
        )
    )
    create_notification(
        db,
        user_id=app.user_id,
        application_id=app.id,
        category="REVIEWER_DECISION",
        title=f"Application {app.reference_code} updated: {new_status.replace('_', ' ')}",
        body=decision_row.reason_text,
        action_url=f"/app/applications/{app.id}"
        if new_status != "NEEDS_MORE_INFO"
        else f"/app/onboarding/{app.id}?step=5",
    )
    audit.add(
        db,
        request,
        "application.decided",
        actor=auth.user,
        resource_type="application",
        resource_id=str(app.id),
        details={
            "reference_code": app.reference_code,
            "decision": body.decision,
            "is_override": is_override,
            "from_status": prev_status,
            "to_status": new_status,
            "reason_codes": body.reason_codes,
        },
    )
    db.flush()
    return decision_row


def reapply_after_rejection(
    db: Session,
    parent_app: Application,
    body: ReapplyRequest,
    auth: AuthContext,
    request: Request,
) -> Application:
    """Create a brand-new DRAFT linked to a previously REJECTED/WITHDRAWN application (distinct from in-place correction & appeal)."""
    if parent_app.status not in ("REJECTED", "WITHDRAWN"):
        raise AppError(
            409,
            "REAPPLY_NOT_ALLOWED",
            "Reapplication is only allowed after an application has been REJECTED or WITHDRAWN. Use in-place Correction for NEEDS_MORE_INFO.",
        )

    open_appeal = db.scalar(
        select(ApplicationAppeal).where(
            ApplicationAppeal.application_id == parent_app.id,
            ApplicationAppeal.status == "OPEN",
        )
    )
    if open_appeal is not None:
        raise AppError(
            409,
            "APPEAL_IN_PROGRESS",
            "An open appeal is already under review for this application. Wait for appeal resolution before starting a new reapplication.",
        )

    existing_active = db.scalar(
        select(Application).where(
            Application.user_id == parent_app.user_id,
            Application.status.in_(ACTIVE_APPLICATION_STATUSES),
        )
    )
    if existing_active is not None:
        raise AppError(
            409,
            "ACTIVE_APPLICATION_EXISTS",
            f"You already have an active application ({existing_active.reference_code}).",
            {"existing_application_id": str(existing_active.id)},
        )

    child = Application(
        reference_code=generate_reference_code(db),
        user_id=parent_app.user_id,
        status="DRAFT",
        current_step=1,
        preferred_language=parent_app.preferred_language,
        channel=parent_app.channel,
        parent_application_id=parent_app.id,
        resolution_kind="REAPPLICATION",
        reapplication_reason=body.reason.strip(),
        full_name=parent_app.full_name,
        date_of_birth=parent_app.date_of_birth,
        gender=parent_app.gender,
        father_or_spouse_name=parent_app.father_or_spouse_name,
        mobile=parent_app.mobile,
        email=parent_app.email,
        address_line1=parent_app.address_line1,
        address_line2=parent_app.address_line2,
        city=parent_app.city,
        district=parent_app.district,
        state=parent_app.state,
        pincode=parent_app.pincode,
        region=parent_app.region,
        same_as_permanent=parent_app.same_as_permanent,
        permanent_address_line1=parent_app.permanent_address_line1,
        permanent_address_line2=parent_app.permanent_address_line2,
        permanent_city=parent_app.permanent_city,
        permanent_state=parent_app.permanent_state,
        permanent_pincode=parent_app.permanent_pincode,
        education_level=parent_app.education_level,
        board_name=parent_app.board_name,
        school_or_university=parent_app.school_or_university,
        passing_year=parent_app.passing_year,
        roll_number=parent_app.roll_number,
        result_status=parent_app.result_status,
        percentage_or_cgpa=parent_app.percentage_or_cgpa,
    )
    db.add(child)
    db.flush()

    db.add(
        ApplicationEvent(
            application_id=parent_app.id,
            actor_user_id=auth.user.id,
            actor_role=auth.user.role.code,
            event_type="REAPPLICATION_STARTED",
            from_status=parent_app.status,
            to_status=parent_app.status,
            summary=f"Started new reapplication {child.reference_code} linked to {parent_app.reference_code}.",
            details={"child_application_id": str(child.id), "child_reference_code": child.reference_code},
        )
    )
    db.add(
        ApplicationEvent(
            application_id=child.id,
            actor_user_id=auth.user.id,
            actor_role=auth.user.role.code,
            event_type="APPLICATION_CREATED",
            from_status=None,
            to_status="DRAFT",
            summary=f"Reapplication draft {child.reference_code} created from {parent_app.reference_code}.",
            details={"parent_application_id": str(parent_app.id), "resolution_kind": "REAPPLICATION"},
        )
    )
    create_notification(
        db,
        user_id=parent_app.user_id,
        application_id=child.id,
        category="APPLICATION",
        title=f"Reapplication {child.reference_code} started",
        body="Update your details and upload fresh KYC documents before submitting your new application.",
        action_url=f"/app/onboarding/{child.id}",
    )
    audit.add(
        db,
        request,
        "application.reapplied",
        actor=auth.user,
        resource_type="application",
        resource_id=str(child.id),
        details={"parent_application_id": str(parent_app.id), "reference_code": child.reference_code},
    )
    db.flush()
    return get_application(db, child.id)


def submit_appeal(
    db: Session,
    app: Application,
    body: AppealCreateRequest,
    auth: AuthContext,
    request: Request,
) -> ApplicationAppeal:
    if app.status != "REJECTED":
        raise AppError(
            409,
            "APPEAL_ONLY_FOR_REJECTED",
            "Formal appeals can only be submitted on REJECTED applications.",
        )

    existing_open = db.scalar(
        select(ApplicationAppeal).where(
            ApplicationAppeal.application_id == app.id,
            ApplicationAppeal.status == "OPEN",
        )
    )
    if existing_open is not None:
        raise AppError(409, "APPEAL_ALREADY_OPEN", "An open appeal already exists for this application.")

    appeal = ApplicationAppeal(
        application_id=app.id,
        submitted_by_user_id=auth.user.id,
        status="OPEN",
        appeal_reason=body.appeal_reason.strip(),
        supporting_notes=body.supporting_notes.strip() if body.supporting_notes else None,
    )
    db.add(appeal)
    app.resolution_kind = "APPEAL"
    app.last_saved_at = utcnow()
    db.flush()

    db.add(
        ApplicationEvent(
            application_id=app.id,
            actor_user_id=auth.user.id,
            actor_role=auth.user.role.code,
            event_type="APPEAL_SUBMITTED",
            from_status=app.status,
            to_status=app.status,
            summary="Applicant filed a formal appeal against rejection.",
            details={"appeal_id": str(appeal.id)},
        )
    )
    create_notification(
        db,
        user_id=app.user_id,
        application_id=app.id,
        category="APPLICATION",
        title=f"Appeal submitted for {app.reference_code}",
        body="A Senior Reviewer will inspect your appeal and supporting explanation.",
        action_url=f"/app/applications/{app.id}",
    )
    audit.add(
        db,
        request,
        "application.appeal_submitted",
        actor=auth.user,
        resource_type="application",
        resource_id=str(app.id),
        details={"reference_code": app.reference_code, "appeal_id": str(appeal.id)},
    )
    db.flush()
    return appeal


def resolve_appeal(
    db: Session,
    app: Application,
    appeal_id: uuid.UUID,
    body: AppealResolveRequest,
    auth: AuthContext,
    request: Request,
) -> ApplicationAppeal:
    appeal = db.scalar(
        select(ApplicationAppeal).where(
            ApplicationAppeal.id == appeal_id,
            ApplicationAppeal.application_id == app.id,
        )
    )
    if appeal is None:
        raise AppError(404, "APPEAL_NOT_FOUND", "Appeal record not found.")
    if appeal.status != "OPEN":
        raise AppError(409, "APPEAL_ALREADY_RESOLVED", "This appeal has already been resolved.")

    now = utcnow()
    prev_status = app.status
    appeal.resolution_notes = body.resolution_notes.strip()
    appeal.resolved_by_user_id = auth.user.id
    appeal.resolved_at = now

    if body.resolution == "UPHOLD_REJECTION":
        appeal.status = "REJECTED_UPHELD"
        new_status = prev_status
        event_type = "APPEAL_UPHELD"
        summary = "Senior Reviewer upheld original rejection upon appeal review."
    elif body.resolution == "REOPEN_FOR_REVIEW":
        appeal.status = "REOPENED"
        new_status = "IN_REVIEW"
        app.status = "IN_REVIEW"
        event_type = "APPEAL_REOPENED"
        summary = "Senior Reviewer reopened application for manual review following appeal."
    else:
        appeal.status = "APPROVED"
        new_status = "KYC_APPROVED"
        app.status = "KYC_APPROVED"
        event_type = "APPEAL_APPROVED"
        summary = "Senior Reviewer approved KYC on appeal."
        latest_exec = db.scalar(
            select(RuleExecution)
            .where(RuleExecution.application_id == app.id)
            .order_by(desc(RuleExecution.executed_at))
            .limit(1)
        )
        db.add(
            ApplicationDecision(
                application_id=app.id,
                rule_execution_id=latest_exec.id if latest_exec else None,
                decided_by_user_id=auth.user.id,
                decided_by_role=auth.user.role.code,
                decision="APPROVE",
                previous_status=prev_status,
                new_status="KYC_APPROVED",
                is_override=True,
                override_of_outcome=latest_exec.outcome if latest_exec else None,
                reason_codes=["REVIEWER_DISCRETION"],
                reason_text=f"Appeal approved: {appeal.resolution_notes}",
                rework_items=[],
            )
        )

    app.last_saved_at = now
    db.add(
        ApplicationEvent(
            application_id=app.id,
            actor_user_id=auth.user.id,
            actor_role=auth.user.role.code,
            event_type=event_type,
            from_status=prev_status,
            to_status=new_status,
            summary=summary,
            details={"appeal_id": str(appeal.id), "resolution": body.resolution},
        )
    )
    create_notification(
        db,
        user_id=app.user_id,
        application_id=app.id,
        category="REVIEWER_DECISION",
        title=f"Appeal outcome for {app.reference_code}: {appeal.status}",
        body=appeal.resolution_notes,
        action_url=f"/app/applications/{app.id}",
    )
    audit.add(
        db,
        request,
        "application.appeal_resolved",
        actor=auth.user,
        resource_type="application",
        resource_id=str(app.id),
        details={"reference_code": app.reference_code, "appeal_id": str(appeal.id), "resolution": body.resolution},
    )
    db.flush()
    return appeal


def get_decision_summary(db: Session, app: Application) -> ApplicationDecisionSummaryOut:
    active_rs = get_active_ruleset(db)
    executions = list(
        db.scalars(
            select(RuleExecution)
            .where(RuleExecution.application_id == app.id)
            .order_by(desc(RuleExecution.executed_at))
        ).all()
    )
    decisions = list(
        db.scalars(
            select(ApplicationDecision)
            .where(ApplicationDecision.application_id == app.id)
            .order_by(desc(ApplicationDecision.created_at))
        ).all()
    )
    appeals = list(
        db.scalars(
            select(ApplicationAppeal)
            .where(ApplicationAppeal.application_id == app.id)
            .order_by(desc(ApplicationAppeal.created_at))
        ).all()
    )
    exec_outs = [RuleExecutionOut.model_validate(e) for e in executions]
    return ApplicationDecisionSummaryOut(
        application_id=app.id,
        application_status=app.status,
        resolution_kind=app.resolution_kind,
        parent_application_id=app.parent_application_id,
        rework_count=app.rework_count,
        active_ruleset_version=active_rs.version,
        latest_execution=exec_outs[0] if exec_outs else None,
        execution_history=exec_outs,
        decisions=[ApplicationDecisionOut.model_validate(d) for d in decisions],
        appeals=[ApplicationAppealOut.model_validate(a) for a in appeals],
    )
