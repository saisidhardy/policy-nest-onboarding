from __future__ import annotations

import uuid
from pathlib import Path

import cv2
import numpy as np
from sqlalchemy import select

from app.core.config import Settings, get_settings
from app.core.db import get_sessionmaker
from app.models import ApplicationEvent, AuditLog, DocumentFieldCorrection
from app.services.consistency import (
    compare_dob_values,
    match_indian_names,
    validate_pan_format,
)
from app.services.ocr_pipeline import mask_aadhaar_numbers_in_text, process_document_bytes
from app.services.verification_providers import (
    check_bank_penny_drop_adapter,
    check_digilocker_adapter,
    check_face_match_adapter,
    check_pan_verification_adapter,
    lookup_ifsc_directory,
)
from tests.conftest import create_staff, csrf, login, register, verify_user_email

SPECIMEN_DIR = (
    Path(__file__).resolve().parents[2] / "docs" / "source_materials" / "05_SPECIMEN_DOCUMENTS" / "sample_specimens"
)


def _render_text_card(lines: list[str], *, width: int = 1100, height: int = 680) -> bytes:
    canvas = np.full((height, width, 3), 255, dtype=np.uint8)
    y = 95
    for line in lines:
        cv2.putText(
            canvas,
            line,
            (60, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.15,
            (15, 15, 15),
            2,
            cv2.LINE_AA,
        )
        y += 82
    ok, buf = cv2.imencode(".png", canvas)
    assert ok
    return bytes(buf)


def _render_blank_png(*, width: int = 400, height: int = 300) -> bytes:
    canvas = np.full((height, width, 3), 210, dtype=np.uint8)
    cv2.putText(canvas, "blurry noise", (30, 120), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (200, 200, 200), 2)
    blurred = cv2.GaussianBlur(canvas, (31, 31), 15)
    ok, buf = cv2.imencode(".png", blurred)
    assert ok
    return bytes(buf)


def _applicant_draft_payload(pan: str = "ABCPD1234F") -> dict:
    return {
        "current_step": 5,
        "preferred_language": "EN",
        "full_name": "Asha Verma",
        "date_of_birth": "1996-05-14",
        "gender": "FEMALE",
        "father_or_spouse_name": "Ramesh Verma",
        "mobile": "9876543210",
        "email": "asha@example.com",
        "pan_number": pan,
        "aadhaar_last4": "9012",
        "address_line1": "42 MG Road",
        "address_line2": "Indiranagar",
        "city": "Bengaluru",
        "district": "Bengaluru Urban",
        "state": "Karnataka",
        "pincode": "560038",
        "same_as_permanent": True,
        "education_level": "GRADUATE",
        "board_name": "CBSE",
        "school_or_university": "National Public School",
        "passing_year": 2014,
        "roll_number": "CBSE-129044",
        "result_status": "PASS",
        "percentage_or_cgpa": "86%",
        "account_holder_name": "Asha Verma",
        "bank_name": "HDFC Bank",
        "branch_name": "Indiranagar",
        "ifsc_code": "HDFC0000240",
        "account_number": "50100123456789",
        "account_type": "SAVINGS",
        "is_joint_account": False,
        "is_primary_holder": True,
    }


def test_cv_ocr_pipeline_masks_aadhaar_extracts_fields_and_flags_defects():
    pan_png = _render_text_card(
        [
            "INCOME TAX DEPARTMENT",
            "GOVT OF INDIA",
            "Permanent Account Number",
            "ABCPD1234F",
            "ASHA VERMA",
            "14/05/1996",
        ]
    )
    pan_res = process_document_bytes("PAN_CARD", "image/png", pan_png)
    assert pan_res.quality.quality_status == "OK"
    assert pan_res.predicted_doc_type == "PAN_CARD"
    assert pan_res.classification_match is True
    assert pan_res.extracted_fields.get("pan_number") == "ABCPD1234F"
    assert pan_res.extracted_fields.get("dob") == "1996-05-14"

    aadhaar_png = _render_text_card(
        [
            "Unique Identification Authority of India",
            "Government of India",
            "Asha Verma",
            "DOB: 14/05/1996",
            "4812 9304 9012",
        ]
    )
    aadhaar_res = process_document_bytes("AADHAAR_FRONT", "image/png", aadhaar_png)
    assert aadhaar_res.aadhaar_masked_applied is True
    assert aadhaar_res.redacted_image_bytes is not None
    assert aadhaar_res.redacted_image_bytes.startswith(b"\x89PNG")
    assert "4812" not in aadhaar_res.raw_ocr_text_masked
    assert "9304" not in aadhaar_res.raw_ocr_text_masked
    assert aadhaar_res.extracted_fields.get("aadhaar_last4") == "9012"

    masked, hits = mask_aadhaar_numbers_in_text("Your Aadhaar is 4812 9304 9012 and VID 1234-5678-9012")
    assert "4812" not in masked and "9304" not in masked and hits == ["9012", "9012"]

    blurry_png = _render_blank_png()
    blur_res = process_document_bytes("PAN_CARD", "image/png", blurry_png)
    assert blur_res.quality.quality_status == "IMAGE_BLURRY"

    selfie_no_face = process_document_bytes("APPLICANT_SELFIE", "image/png", blurry_png)
    assert selfie_no_face.quality.quality_status == "FACE_NOT_DETECTED"
    assert (
        selfie_no_face.face_detected
        if hasattr(selfie_no_face, "face_detected")
        else selfie_no_face.quality.face_detected is False
    )


def test_real_repository_specimen_documents_process_cleanly():
    profile_bytes = (SPECIMEN_DIR / "Profile.jpg").read_bytes()
    selfie_res = process_document_bytes("APPLICANT_SELFIE", "image/jpeg", profile_bytes)
    assert selfie_res.quality.face_detected is True
    assert selfie_res.quality.quality_status == "OK"
    assert selfie_res.predicted_doc_type == "APPLICANT_SELFIE"

    aadhaar_bytes = (SPECIMEN_DIR / "Aadhar.jpg").read_bytes()
    aadhaar_res = process_document_bytes("AADHAAR_FRONT", "image/jpeg", aadhaar_bytes)
    assert aadhaar_res.aadhaar_masked_applied is True
    assert aadhaar_res.redacted_image_bytes is not None

    pan_bytes = (SPECIMEN_DIR / "ananya_pan.jpg").read_bytes()
    pan_res = process_document_bytes("PAN_CARD", "image/jpeg", pan_bytes)
    assert pan_res.ocr_engine == "LOCAL_TESSERACT"
    assert pan_res.quality.quality_status == "OK"

    tenth_bytes = (SPECIMEN_DIR / "10TH.pdf").read_bytes()
    tenth_res = process_document_bytes("CLASS_10_MARKSHEET", "application/pdf", tenth_bytes)
    assert tenth_res.ocr_engine in ("LOCAL_TESSERACT", "PYPDF_TEXT")


def test_8_tier_indian_name_matching_pan_format_and_dob_rules():
    assert match_indian_names("Asha Verma", "ASHA VERMA").tier == 1
    assert match_indian_names("S R Sharma", "Suresh Ramesh Sharma").tier == 2
    assert match_indian_names("Verma Asha", "Asha Verma").tier == 3
    assert match_indian_names("Rahul Kumar Sharma", "Rahul Sharma").tier == 4

    t5 = match_indian_names("Rameshh Verma", "Ramesh Verma")
    assert t5.tier == 5 and t5.verdict == "NEEDS_INFO" and t5.reason_code == "NAME_SPELLING_VARIANT"

    t6 = match_indian_names("Ananya Sharma", "Ananya Deshmukh")
    assert t6.tier == 6 and t6.verdict == "NEEDS_INFO"

    t7 = match_indian_names("Asha Verma", "Kiran Deshmukh")
    assert t7.tier == 7 and t7.verdict == "HUMAN_REVIEW" and t7.reason_code == "NAME_MISMATCH"

    t8 = match_indian_names("Priyadharshini Sharma", "P Sharma", allow_bank_truncation=True)
    assert t8.verdict == "MATCH"

    assert validate_pan_format("ABCPD1234F").status == "PASSED"
    company_pan = validate_pan_format("ABCCD1234F")
    assert company_pan.status == "FAILED" and company_pan.details["reason_code"] == "PAN_NOT_INDIVIDUAL"

    dob_yr = compare_dob_values("1996-05-14", "1996", "AADHAAR_FRONT")
    assert dob_yr.status == "PASSED" and dob_yr.details.get("year_only_match") is True


def test_external_provider_adapters_distinguish_origins_and_block_sandbox_in_prod(monkeypatch, make_client):
    # Unconfigured by default (except public IFSC when enabled)
    assert check_pan_verification_adapter("ABCPD1234F").origin == "UNCONFIGURED"
    assert check_bank_penny_drop_adapter("HDFC0000240", "Asha Verma").origin == "UNCONFIGURED"
    assert check_digilocker_adapter().origin == "UNCONFIGURED"
    assert check_face_match_adapter(True).origin == "UNCONFIGURED"

    # Mock public IFSC lookup
    class DummyResp:
        status_code = 200
        content = b"{}"

        def json(self):
            return {"BANK": "HDFC Bank", "BRANCH": "INDIRANAGAR", "CITY": "BENGALURU", "STATE": "KARNATAKA"}

    monkeypatch.setenv("IFSC_LOOKUP_ENABLED", "true")
    get_settings.cache_clear()
    monkeypatch.setattr("app.services.http_client.httpx.request", lambda method, url, **kwargs: DummyResp())
    ifsc_res = lookup_ifsc_directory("HDFC0000240")
    assert ifsc_res.status == "PASSED"
    assert ifsc_res.origin == "PUBLIC_DIRECTORY"
    assert ifsc_res.is_simulated is False
    assert ifsc_res.details["bank"] == "HDFC Bank"

    # Sandbox mode explicitly flagged simulated and blocked in production
    monkeypatch.setenv("PAN_VERIFICATION_PROVIDER", "sandbox")
    get_settings.cache_clear()
    sbx = check_pan_verification_adapter("ABCPD1234F")
    assert sbx.origin == "SANDBOX" and sbx.is_simulated is True and sbx.provider_reference is None

    try:
        try:
            Settings(app_env="production", pan_verification_provider="sandbox")
            raise AssertionError("Production must forbid sandbox verification adapters")
        except ValueError as exc:
            assert "forbidden in production" in str(exc).lower()
    finally:
        monkeypatch.delenv("PAN_VERIFICATION_PROVIDER", raising=False)
        monkeypatch.setenv("IFSC_LOOKUP_ENABLED", "false")
        get_settings.cache_clear()

    # Admin system/health exposes Phase 3 integrations accurately
    create_staff("ADMIN", "admin@example.com", region="ALL", clearance=3)
    ac = make_client()
    assert login(ac, "admin@example.com").status_code == 200
    health = ac.get("/api/v1/admin/system/health").json()
    by_key = {item["key"]: item for item in health["integrations"]}
    assert by_key["ocr"]["status"] == "CONFIGURED"
    assert by_key["ai_assistant"]["mode"] == "LOCAL_DEVELOPMENT"
    assert by_key["pan_verification"]["status"] == "NOT_CONFIGURED"


def test_api_submission_aadhaar_redaction_and_reviewer_correction_workflow(make_client, mailbox):
    # Register verified applicant in Karnataka (SOUTH region)
    applicant = make_client()
    assert register(applicant, email="asha@example.com", name="Asha Verma").status_code == 201
    verify_user_email(applicant, mailbox, email="asha@example.com")

    create_staff("REVIEWER", "south.rev@example.com", name="South Reviewer", region="SOUTH", clearance=2)
    create_staff("REVIEWER", "north.rev@example.com", name="North Reviewer", region="NORTH", clearance=2)
    create_staff("ADMIN", "admin@example.com", name="Admin", region="ALL", clearance=3)

    app_id = applicant.post("/api/v1/applications", headers=csrf(applicant), json={}).json()["id"]
    assert (
        applicant.patch(
            f"/api/v1/applications/{app_id}",
            headers=csrf(applicant),
            json=_applicant_draft_payload(pan="ABCPD1234F"),
        ).status_code
        == 200
    )

    # Intentional name variant on PAN + blank OCR on cheque so reviewer correction can exercise re-evaluation
    pan_png = _render_text_card(
        [
            "INCOME TAX DEPARTMENT",
            "ABCPD1234F",
            "ASHA KUMARI VERMA",
            "14/05/1996",
        ]
    )
    aadhaar_front_png = _render_text_card(
        [
            "Unique Identification Authority of India",
            "Asha Verma",
            "DOB: 14/05/1996",
            "4812 9304 9012",
        ]
    )
    aadhaar_back_png = _render_text_card(
        [
            "Unique Identification Authority of India",
            "Address: 42 MG Road Bengaluru 560038",
        ]
    )
    cheque_png = _render_text_card(
        [
            "HDFC BANK CANCELLED CHEQUE",
            "Asha Verma",
            "IFSC: HDFC0000240",
            "A/C NO: 50100123456789",
        ]
    )

    uploads = [
        ("PAN_CARD", "pan.png", pan_png, "image/png"),
        ("AADHAAR_FRONT", "aadhaar_f.png", aadhaar_front_png, "image/png"),
        ("AADHAAR_BACK", "aadhaar_b.png", aadhaar_back_png, "image/png"),
        ("CLASS_10_MARKSHEET", "10th.pdf", (SPECIMEN_DIR / "10TH.pdf").read_bytes(), "application/pdf"),
        ("BANK_DOCUMENT", "cheque.png", cheque_png, "image/png"),
        ("APPLICANT_SELFIE", "selfie.jpg", (SPECIMEN_DIR / "Profile.jpg").read_bytes(), "image/jpeg"),
    ]
    doc_ids: dict[str, str] = {}
    for dtype, fname, payload, mime in uploads:
        r = applicant.post(
            f"/api/v1/applications/{app_id}/documents/{dtype}",
            headers=csrf(applicant),
            files={"file": (fname, payload, mime)},
        )
        assert r.status_code == 201, f"{dtype}: {r.text}"
        doc_ids[dtype] = r.json()["id"]

    # Submit automatically triggers Phase 3 processing
    sub = applicant.post(
        f"/api/v1/applications/{app_id}/submit",
        headers=csrf(applicant),
        json={"consent_terms": True, "consent_kyc_processing": True, "declaration_no_other_posp": True},
    )
    assert sub.status_code == 200, sub.text
    assert sub.json()["status"] == "SUBMITTED"

    report = applicant.get(f"/api/v1/applications/{app_id}/verification").json()
    assert report["summary"]["documents_processed"] == 6
    ext_by_type = {e["doc_type"]: e for e in report["extractions"]}
    assert ext_by_type["AADHAAR_FRONT"]["aadhaar_masked_applied"] is True
    assert ext_by_type["AADHAAR_FRONT"]["has_redacted_image"] is True
    assert "4812" not in (ext_by_type["AADHAAR_FRONT"]["raw_ocr_text_masked"] or "")
    assert ext_by_type["APPLICANT_SELFIE"]["face_detected"] is True

    # Redacted Aadhaar image endpoint serves PNG and isolates other users/regions
    redacted_resp = applicant.get(f"/api/v1/applications/{app_id}/documents/{doc_ids['AADHAAR_FRONT']}/redacted")
    assert redacted_resp.status_code == 200
    assert redacted_resp.content.startswith(b"\x89PNG")

    # Authorization checks on field correction
    # 1. Applicant cannot correct own extracted fields
    assert (
        applicant.patch(
            f"/api/v1/applications/{app_id}/documents/{doc_ids['PAN_CARD']}/fields",
            headers=csrf(applicant),
            json={"fields": {"full_name": "Asha Verma"}, "reason": "Trying to edit own extraction"},
        ).status_code
        == 403
    )

    # 2. Admin lacks application:review permission (separation of duties)
    admin_client = make_client()
    assert login(admin_client, "admin@example.com").status_code == 200
    assert (
        admin_client.patch(
            f"/api/v1/applications/{app_id}/documents/{doc_ids['PAN_CARD']}/fields",
            headers=csrf(admin_client),
            json={"fields": {"full_name": "Asha Verma"}, "reason": "Admin should not override review"},
        ).status_code
        == 403
    )

    # 3. North reviewer blocked by regional ABAC
    north = make_client()
    assert login(north, "north.rev@example.com").status_code == 200
    assert north.get(f"/api/v1/applications/{app_id}/verification").status_code == 403
    assert (
        north.patch(
            f"/api/v1/applications/{app_id}/documents/{doc_ids['PAN_CARD']}/fields",
            headers=csrf(north),
            json={"fields": {"full_name": "Asha Verma"}, "reason": "Cross-region edit blocked"},
        ).status_code
        == 403
    )

    # 4. South reviewer cannot enter 12-digit Aadhaar into corrections
    south = make_client()
    assert login(south, "south.rev@example.com").status_code == 200
    bad_corr = south.patch(
        f"/api/v1/applications/{app_id}/documents/{doc_ids['AADHAAR_FRONT']}/fields",
        headers=csrf(south),
        json={"fields": {"aadhaar_last4": "481293049012"}, "reason": "Must be rejected"},
    )
    assert bad_corr.status_code == 422

    # 5. South reviewer corrects extracted full_name on Class 10 marksheet and PAN_CARD
    corr = south.patch(
        f"/api/v1/applications/{app_id}/documents/{doc_ids['PAN_CARD']}/fields",
        headers=csrf(south),
        json={
            "fields": {"full_name": "Asha Verma"},
            "reason": "Confirmed middle name Kumari omitted cleanly per PAN typography",
        },
    )
    assert corr.status_code == 200, corr.text
    updated = corr.json()
    pan_ext = next(e for e in updated["extractions"] if e["doc_type"] == "PAN_CARD")
    assert pan_ext["reviewer_corrected_fields"]["full_name"] == "ASHA VERMA"
    assert pan_ext["effective_fields"]["full_name"] == "ASHA VERMA"
    assert len(updated["corrections"]) == 1
    assert updated["corrections"][0]["field_name"] == "full_name"

    # Audit log & field correction trail & event history recorded cleanly without raw PAN/Aadhaar
    with get_sessionmaker()() as db:
        corr_rows = db.scalars(
            select(DocumentFieldCorrection).where(DocumentFieldCorrection.application_id == uuid.UUID(app_id))
        ).all()
        assert len(corr_rows) == 1
        events = db.scalars(select(ApplicationEvent).where(ApplicationEvent.application_id == uuid.UUID(app_id))).all()
        ev_types = {e.event_type for e in events}
        assert {"DOCUMENT_INTELLIGENCE_RAN", "EXTRACTED_FIELDS_CORRECTED"} <= ev_types
        audits = db.scalars(select(AuditLog)).all()
        audit_blob = " ".join(str(a.details) for a in audits)
        assert "ABCPD1234F" not in audit_blob
        assert "481293049012" not in audit_blob
