"""Tests for multimodal Gemini Vision OCR, upload auto-checks, selfie-vs-ID face screening, and preview headers."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch

import cv2
import numpy as np

from app.services.cv_quality import ImageQualityMetrics as QualityMetrics
from app.services.cv_quality import analyze_image_quality, compare_selfie_to_id_opencv
from app.services.gemini_vision import compare_faces_with_gemini_vision, enhance_ocr_result_with_gemini_vision
from app.services.ocr_pipeline import OcrPipelineResult
from app.services.platform_config import EffectiveIntegrationsConfig
from app.services.verification_providers import evaluate_selfie_id_face_comparison
from tests.conftest import csrf, register, verify_user_email


def _dummy_cfg(api_key: str | None = "test-gem-key") -> EffectiveIntegrationsConfig:
    return EffectiveIntegrationsConfig(
        ocr_provider="local_tesseract",
        ocr_api_base_url=None,
        ocr_api_key=None,
        ai_provider="gemini" if api_key else "local_heuristic",
        gemini_model="gemini-3.8-flash",
        gemini_api_key=api_key,
        ifsc_lookup_enabled=False,
        pan_verification_provider="not_configured",
        pan_api_base_url=None,
        pan_api_key=None,
        bank_verification_provider="not_configured",
        bank_api_base_url=None,
        bank_api_key=None,
        digilocker_provider="not_configured",
        digilocker_base_url=None,
        digilocker_client_id=None,
        digilocker_client_secret=None,
        face_match_provider="not_configured",
        face_api_base_url=None,
        face_api_key=None,
        sms_provider="none",
        sms_api_base_url=None,
        sms_api_key=None,
        sms_sender_id=None,
        sms_timeout_seconds=10,
        sms_max_attempts=1,
        webhook_shared_secret=None,
        integration_http_timeout_seconds=10,
        integration_http_max_retries=1,
        source="environment",
    )


def _blank_png(color: int = 255) -> bytes:
    canvas = np.full((320, 480, 3), color, dtype=np.uint8)
    ok, buf = cv2.imencode(".png", canvas)
    assert ok
    return bytes(buf)


def _sharp_card_png() -> bytes:
    canvas = np.full((500, 800, 3), 245, dtype=np.uint8)
    cv2.rectangle(canvas, (30, 30), (770, 470), (20, 40, 120), 4)
    cv2.putText(canvas, "INCOME TAX DEPARTMENT ABCPD1234F", (60, 140), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (10, 10, 10), 2)
    ok, buf = cv2.imencode(".png", canvas)
    assert ok
    return bytes(buf)


def test_blank_canvas_flagged_unreadable_and_gemini_vision_enhances_ocr():
    blank_q = analyze_image_quality(_blank_png())
    assert blank_q.quality_status == "UNREADABLE"

    base_res = OcrPipelineResult(
        ocr_engine="OCR_UNAVAILABLE",
        predicted_doc_type="UNKNOWN",
        classification_confidence=0.0,
        classification_match=False,
        quality=QualityMetrics(
            quality_status="OK",
            blur_score=180.0,
            glare_ratio=0.0,
            edge_clip_ratio=0.01,
            face_detected=None,
            width=800,
            height=500,
        ),
        ocr_confidence=None,
        raw_ocr_text_masked="",
        extracted_fields={},
        missing_fields=["pan_number", "full_name", "dob"],
        aadhaar_masked_applied=False,
        redacted_image_bytes=None,
    )

    payload = json.dumps(
        {
            "predicted_doc_type": "PAN_CARD",
            "classification_confidence": 0.96,
            "is_valid_document": True,
            "is_blurry": False,
            "has_heavy_glare": False,
            "is_cropped": False,
            "appears_blank_or_fake": False,
            "face_detected": True,
            "ocr_confidence": 0.94,
            "transcribed_text_masked": "INCOME TAX DEPARTMENT ABCPD1234F ASHA VERMA 14/05/1996 4812 9304 9012",
            "quality_feedback": "Sharp PAN card scan.",
            "fields": {
                "pan_number": "ABCPD1234F",
                "full_name": "ASHA VERMA",
                "dob": "14/05/1996",
            },
        }
    )

    class _FakeInteractions:
        def create(self, **kwargs):
            return SimpleNamespace(output_text=payload)

    fake_client = SimpleNamespace(interactions=_FakeInteractions())
    with patch("google.genai.Client", return_value=fake_client):
        upgraded = enhance_ocr_result_with_gemini_vision(
            doc_type="PAN_CARD",
            content_type="image/png",
            raw_bytes=_sharp_card_png(),
            res=base_res,
            cfg=_dummy_cfg(),
        )

    assert upgraded.ocr_engine == "GEMINI_VISION"
    assert upgraded.predicted_doc_type == "PAN_CARD"
    assert upgraded.classification_match is True
    assert upgraded.extracted_fields["pan_number"] == "ABCPD1234F"
    assert upgraded.extracted_fields["dob"] == "1996-05-14"
    assert upgraded.aadhaar_masked_applied is True
    assert "4812" not in upgraded.raw_ocr_text_masked

    face_payload = json.dumps(
        {
            "selfie_has_clear_face": True,
            "aadhaar_face_detected": True,
            "aadhaar_match_score": 0.89,
            "pan_face_detected": True,
            "pan_match_score": 0.84,
            "overall_match_score": 0.87,
            "verdict": "MATCH",
            "reasoning": "Facial geometry matches across selfie, Aadhaar, and PAN.",
        }
    )
    fake_face_client = SimpleNamespace(interactions=SimpleNamespace(create=lambda **kw: SimpleNamespace(output_text=face_payload)))
    with patch("google.genai.Client", return_value=fake_face_client):
        cmp_res = compare_faces_with_gemini_vision(
            selfie_bytes=_sharp_card_png(),
            selfie_mime="image/png",
            aadhaar_bytes=_sharp_card_png(),
            aadhaar_mime="image/png",
            cfg=_dummy_cfg(),
        )
    assert cmp_res is not None
    assert cmp_res.verdict == "MATCH"
    assert cmp_res.overall_match_score == 0.87


def test_opencv_face_comparison_reports_honest_missing_faces():
    res = compare_selfie_to_id_opencv(
        selfie_bytes=_sharp_card_png(),
        selfie_mime="image/png",
        aadhaar_bytes=_sharp_card_png(),
        aadhaar_mime="image/png",
    )
    assert res["selfie_face_detected"] is False
    assert evaluate_selfie_id_face_comparison({}).status == "NEEDS_INFO"


def test_upload_auto_processes_and_content_allows_sameorigin_iframe(make_client, mailbox):
    client = make_client()
    assert register(client, email="preview.user@example.com", name="Preview User").status_code == 201
    verify_user_email(client, mailbox, email="preview.user@example.com")

    app_id = client.post("/api/v1/applications", headers=csrf(client), json={}).json()["id"]
    up = client.post(
        f"/api/v1/applications/{app_id}/documents/PAN_CARD",
        headers=csrf(client),
        files={"file": ("blank.png", _blank_png(), "image/png")},
    )
    assert up.status_code == 201, up.text
    body = up.json()
    assert body["extraction"] is not None
    assert body["extraction"]["quality_status"] == "UNREADABLE"

    content = client.get(f"/api/v1/applications/{app_id}/documents/{body['id']}/content")
    assert content.status_code == 200
    assert content.headers.get("x-frame-options") == "SAMEORIGIN"


def test_cross_slot_document_mismatch_rejected_with_422(make_client, mailbox):
    from pathlib import Path

    spec_dir = Path(__file__).resolve().parents[2] / "docs" / "source_materials" / "05_SPECIMEN_DOCUMENTS" / "sample_specimens"
    client = make_client()
    assert register(client, email="mismatch.user@example.com", name="Mismatch User").status_code == 201
    verify_user_email(client, mailbox, email="mismatch.user@example.com")
    app_id = client.post("/api/v1/applications", headers=csrf(client), json={}).json()["id"]

    # Render an explicit Aadhaar Back card
    canvas = np.full((420, 680, 3), 245, dtype=np.uint8)
    cv2.putText(canvas, "Unique Identification Authority of India", (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (10, 10, 10), 2)
    cv2.putText(canvas, "Address: S/O Ramesh 42 MG Road Bengaluru 560038", (30, 160), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (10, 10, 10), 2)
    ok, buf = cv2.imencode(".png", canvas)
    assert ok
    aadhaar_back_png = bytes(buf)

    pan_pdf = (spec_dir / "PAN.pdf").read_bytes()
    aadhaar_front_jpg = (spec_dir / "Aadhar.jpg").read_bytes()
    selfie_jpg = (spec_dir / "Profile.jpg").read_bytes()

    # 1. PAN.pdf uploaded to AADHAAR_FRONT -> 422 DOCUMENT_TYPE_MISMATCH
    r1 = client.post(
        f"/api/v1/applications/{app_id}/documents/AADHAAR_FRONT",
        headers=csrf(client),
        files={"file": ("PAN.pdf", pan_pdf, "application/pdf")},
    )
    assert r1.status_code == 422, r1.text
    assert r1.json()["error"]["code"] == "DOCUMENT_TYPE_MISMATCH"
    assert r1.json()["error"]["details"]["predicted_doc_type"] == "PAN_CARD"

    # 2. Aadhar.jpg (front) uploaded to AADHAAR_BACK -> 422 DOCUMENT_TYPE_MISMATCH
    r2 = client.post(
        f"/api/v1/applications/{app_id}/documents/AADHAAR_BACK",
        headers=csrf(client),
        files={"file": ("Aadhar.jpg", aadhaar_front_jpg, "image/jpeg")},
    )
    assert r2.status_code == 422, r2.text
    assert r2.json()["error"]["code"] == "DOCUMENT_TYPE_MISMATCH"
    assert r2.json()["error"]["details"]["predicted_doc_type"] == "AADHAAR_FRONT"

    # 3. Aadhaar Back uploaded to AADHAAR_FRONT -> 422 DOCUMENT_TYPE_MISMATCH
    r3 = client.post(
        f"/api/v1/applications/{app_id}/documents/AADHAAR_FRONT",
        headers=csrf(client),
        files={"file": ("aadhaar_back.png", aadhaar_back_png, "image/png")},
    )
    assert r3.status_code == 422, r3.text
    assert r3.json()["error"]["code"] == "DOCUMENT_TYPE_MISMATCH"
    assert r3.json()["error"]["details"]["predicted_doc_type"] == "AADHAAR_BACK"

    # 4. Selfie uploaded to PAN_CARD -> 422 DOCUMENT_TYPE_MISMATCH
    r4 = client.post(
        f"/api/v1/applications/{app_id}/documents/PAN_CARD",
        headers=csrf(client),
        files={"file": ("Profile.jpg", selfie_jpg, "image/jpeg")},
    )
    assert r4.status_code == 422, r4.text
    assert r4.json()["error"]["code"] == "DOCUMENT_TYPE_MISMATCH"
    assert r4.json()["error"]["details"]["predicted_doc_type"] == "APPLICANT_SELFIE"

    # 5. Aadhar.jpg uploaded to APPLICANT_SELFIE -> 422 DOCUMENT_TYPE_MISMATCH
    r5 = client.post(
        f"/api/v1/applications/{app_id}/documents/APPLICANT_SELFIE",
        headers=csrf(client),
        files={"file": ("Aadhar.jpg", aadhaar_front_jpg, "image/jpeg")},
    )
    assert r5.status_code == 422, r5.text
    assert r5.json()["error"]["code"] == "DOCUMENT_TYPE_MISMATCH"
    assert r5.json()["error"]["details"]["predicted_doc_type"] == "AADHAAR_FRONT"

    # 6. Correct slots succeed with 201 and verified match
    ok_pan = client.post(
        f"/api/v1/applications/{app_id}/documents/PAN_CARD",
        headers=csrf(client),
        files={"file": ("PAN.pdf", pan_pdf, "application/pdf")},
    )
    assert ok_pan.status_code == 201, ok_pan.text
    assert ok_pan.json()["extraction"]["predicted_doc_type"] == "PAN_CARD"
    assert ok_pan.json()["extraction"]["classification_match"] is True

    ok_af = client.post(
        f"/api/v1/applications/{app_id}/documents/AADHAAR_FRONT",
        headers=csrf(client),
        files={"file": ("Aadhar.jpg", aadhaar_front_jpg, "image/jpeg")},
    )
    assert ok_af.status_code == 201, ok_af.text
    assert ok_af.json()["extraction"]["predicted_doc_type"] == "AADHAAR_FRONT"
    assert ok_af.json()["extraction"]["classification_match"] is True

    ok_ab = client.post(
        f"/api/v1/applications/{app_id}/documents/AADHAAR_BACK",
        headers=csrf(client),
        files={"file": ("aadhaar_back.png", aadhaar_back_png, "image/png")},
    )
    assert ok_ab.status_code == 201, ok_ab.text
    assert ok_ab.json()["extraction"]["predicted_doc_type"] == "AADHAAR_BACK"
    assert ok_ab.json()["extraction"]["classification_match"] is True
