import hashlib
import hmac
import json
import smtplib
import uuid
from unittest.mock import patch

import httpx
import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.models import (
    ApplicationEvent,
    AuditLog,
    SmsDelivery,
    SystemConfig,
    User,
    VerificationCheck,
    WebhookDelivery,
)
from app.services.ai_assistant import GeminiAIAssistant, LocalHeuristicAIAssistant, get_ai_assistant
from app.services.email import STATUS_SENT, OutgoingEmail, build_email, deliver_with_retry
from app.services.http_client import request_json_with_retry
from app.services.notifications import create_notification
from app.services.ocr_pipeline import process_document_bytes
from app.services.sms import (
    SMS_STATUS_FAILED,
    SMS_STATUS_NOT_CONFIGURED,
    SMS_STATUS_SANDBOX,
    SMS_STATUS_SENT,
    send_sms_notification,
)
from app.services.verification_providers import (
    check_bank_penny_drop_adapter,
    check_digilocker_adapter,
    check_face_match_adapter,
    check_pan_verification_adapter,
)
from tests.conftest import create_staff, csrf, login
from tests.test_applications import _complete_draft_payload, _verified_applicant
from tests.test_phase6_training import _create_kyc_approved_app


def _sign(secret: str, raw: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()


def _base_integrations_payload(**overrides) -> dict:
    payload = {
        "ocr_provider": "local_tesseract",
        "ocr_api_base_url": None,
        "ocr_api_key": None,
        "clear_ocr_api_key": False,
        "ai_provider": "local_heuristic",
        "gemini_model": "gemini-3.8-flash",
        "gemini_api_key": None,
        "clear_gemini_api_key": False,
        "ifsc_lookup_enabled": True,
        "pan_verification_provider": "not_configured",
        "pan_api_base_url": None,
        "pan_api_key": None,
        "clear_pan_api_key": False,
        "bank_verification_provider": "not_configured",
        "bank_api_base_url": None,
        "bank_api_key": None,
        "clear_bank_api_key": False,
        "digilocker_provider": "not_configured",
        "digilocker_base_url": None,
        "digilocker_client_id": None,
        "digilocker_client_secret": None,
        "clear_digilocker_client_secret": False,
        "face_match_provider": "not_configured",
        "face_api_base_url": None,
        "face_api_key": None,
        "clear_face_api_key": False,
        "sms_provider": "not_configured",
        "sms_api_base_url": None,
        "sms_sender_id": None,
        "sms_timeout_seconds": 8,
        "sms_max_attempts": 3,
        "sms_api_key": None,
        "clear_sms_api_key": False,
        "webhook_shared_secret": None,
        "clear_webhook_shared_secret": False,
        "integration_http_timeout_seconds": 8,
        "integration_http_max_retries": 2,
    }
    payload.update(overrides)
    return payload


def test_http_client_retries_transient_503_and_handles_timeout():
    calls = {"count": 0}

    def fake_request(method, url, headers=None, json=None, timeout=None):
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(503, json={"error": "upstream busy"})
        return httpx.Response(200, json={"verified": True, "reference_id": "REF-RETRY-1"})

    with patch("app.services.http_client.httpx.request", side_effect=fake_request):
        res = request_json_with_retry("POST", "https://vendor.test/check", backoff_base_seconds=0.0, max_retries=2)

    assert res.ok is True
    assert res.attempts == 2
    assert res.status_code == 200
    assert res.data["reference_id"] == "REF-RETRY-1"

    with patch("app.services.http_client.httpx.request", side_effect=httpx.ReadTimeout("timed out")):
        res_to = request_json_with_retry(
            "POST", "https://vendor.test/check", timeout_seconds=1.0, max_retries=1, backoff_base_seconds=0.0
        )
    assert res_to.ok is False
    assert res_to.attempts == 2
    assert res_to.error_code == "TIMEOUT"


def test_email_retry_and_db_public_url(make_client, mailbox):
    create_staff("ADMIN", "email.admin@example.com", "Email Admin", region="ALL")
    adm = make_client()
    login(adm, "email.admin@example.com")

    adm.put(
        "/api/v1/admin/config/platform",
        json={
            "public_app_url": "https://onboarding.policynest.example",
            "require_email_verification": True,
            "session_idle_minutes": 45,
            "login_max_failures": 5,
            "login_lockout_minutes": 15,
            "max_upload_size_mb": 10,
        },
        headers=csrf(adm),
    ).raise_for_status()

    class _FlakyProvider:
        name = "smtp_flaky"
        configured = True

        def __init__(self):
            self.calls = 0

        def send(self, msg: OutgoingEmail) -> None:
            self.calls += 1
            if self.calls == 1:
                raise smtplib.SMTPServerDisconnected("transient drop")

    provider = _FlakyProvider()
    msg = OutgoingEmail(to="a@b.com", subject="Hi", text="Hello", html="<p>Hello</p>")
    with patch("app.services.email.time.sleep"):
        st, attempts, err = deliver_with_retry(provider, msg, max_attempts=3)
    assert st == STATUS_SENT
    assert attempts == 2
    assert err is None

    with get_sessionmaker()() as db:
        u = db.scalar(select(User).where(User.email == "email.admin@example.com"))
        built = build_email("password_reset", u, "tok123", db=db)
        assert "https://onboarding.policynest.example/reset-password?token=tok123" in built.text


def test_sms_adapters_milestone_dispatch_and_retry_failed(make_client, mailbox):
    create_staff("ADMIN", "sms.admin@example.com", "SMS Admin", region="ALL")
    adm = make_client()
    login(adm, "sms.admin@example.com")

    applicant_client = _verified_applicant(make_client, mailbox, email="sms.user@example.com", name="SMS User")
    app_id = applicant_client.post("/api/v1/applications", json={}, headers=csrf(applicant_client)).json()["id"]

    # 1. Default unconfigured -> honest NOT_CONFIGURED, no simulated flag
    with get_sessionmaker()() as db:
        u = db.scalar(select(User).where(User.email == "sms.user@example.com"))
        row = send_sms_notification(db, mobile="+919876543210", event_type="TEST", message="Hello", user_id=u.id)
        db.commit()
        assert row is not None
        assert row.status == SMS_STATUS_NOT_CONFIGURED
        assert row.is_simulated is False
        assert row.provider_message_id is None
        assert row.attempts == 0

    # 2. Sandbox SMS fixture + production guard + milestone notification auto-dispatch
    adm.put(
        "/api/v1/admin/config/integrations",
        json=_base_integrations_payload(sms_provider="sandbox"),
        headers=csrf(adm),
    ).raise_for_status()

    with get_sessionmaker()() as db:
        u = db.scalar(select(User).where(User.email == "sms.user@example.com"))
        notif = create_notification(
            db,
            user_id=u.id,
            application_id=uuid.UUID(app_id),
            title="Application submitted",
            body="Your POSP onboarding application PN-TEST has been received.",
            category="APPLICATION",
        )
        db.commit()
        assert notif.category == "APPLICATION"
        sms_rows = db.scalars(select(SmsDelivery).where(SmsDelivery.application_id == uuid.UUID(app_id))).all()
        assert len(sms_rows) == 1
        assert sms_rows[0].status == SMS_STATUS_SANDBOX
        assert sms_rows[0].is_simulated is True
        assert sms_rows[0].provider_message_id is None

        s = get_settings()
        old_env = s.app_env
        s.app_env = "production"
        try:
            with pytest.raises(RuntimeError, match="forbidden in production"):
                send_sms_notification(db, mobile=u.mobile, event_type="PROD_CHECK", message="test")
        finally:
            s.app_env = old_env

    # 3. Live HTTP SMS provider: fail first, then retry-failed endpoint succeeds
    adm.put(
        "/api/v1/admin/config/integrations",
        json=_base_integrations_payload(
            sms_provider="twilio",
            sms_api_base_url="https://sms.vendor.test/v1/messages",
            sms_api_key="sms-secret-key-999",
            sms_sender_id="PLCNST",
            sms_max_attempts=1,
        ),
        headers=csrf(adm),
    ).raise_for_status()

    with (
        patch("app.services.http_client.httpx.request", return_value=httpx.Response(500, json={"error": "down"})),
        get_sessionmaker()() as db,
    ):
        u = db.scalar(select(User).where(User.email == "sms.user@example.com"))
        fail_row = send_sms_notification(
            db, mobile=u.mobile, event_type="SUBMIT", message="App submitted", user_id=u.id
        )
        db.commit()
        assert fail_row is not None
        assert fail_row.status == SMS_STATUS_FAILED
        assert fail_row.provider_message_id is None

    with patch(
        "app.services.http_client.httpx.request",
        return_value=httpx.Response(200, json={"message_id": "SM-VENDOR-777"}),
    ):
        r_retry = adm.post("/api/v1/admin/integrations/sms/retry-failed", headers=csrf(adm))
    assert r_retry.status_code == 200
    assert r_retry.json()["attempted"] == 1
    assert r_retry.json()["succeeded"] == 1
    assert r_retry.json()["failed"] == 0

    with get_sessionmaker()() as db:
        refreshed = db.get(SmsDelivery, fail_row.id)
        assert refreshed.status == SMS_STATUS_SENT
        assert refreshed.provider_message_id == "SM-VENDOR-777"
        assert refreshed.is_simulated is False


def test_commercial_verification_adapters_ocr_http_and_ai_resolution(make_client, mailbox):
    create_staff("ADMIN", "vendor.admin@example.com", "Vendor Admin", region="ALL")
    adm = make_client()
    login(adm, "vendor.admin@example.com")

    # Select commercial providers WITHOUT URL/key -> must honestly report NOT_CONFIGURED
    adm.put(
        "/api/v1/admin/config/integrations",
        json=_base_integrations_payload(
            ocr_provider="http_ocr",
            ai_provider="gemini",
            pan_verification_provider="protean",
            bank_verification_provider="razorpayx",
            digilocker_provider="negd_oauth",
            face_match_provider="aws_rekognition",
        ),
        headers=csrf(adm),
    ).raise_for_status()

    with get_sessionmaker()() as db:
        assert check_pan_verification_adapter("ABCDE1234F", full_name="Asha", db=db).status == "NOT_CONFIGURED"
        assert check_bank_penny_drop_adapter("HDFC0000240", "Asha", db=db).status == "NOT_CONFIGURED"
        assert check_digilocker_adapter(application_id="app-1", db=db).status == "NOT_CONFIGURED"
        assert check_face_match_adapter(True, application_id="app-1", db=db).status == "NOT_CONFIGURED"
        # Gemini without API key falls back cleanly to LocalHeuristicAssistant
        assert isinstance(get_ai_assistant(db), LocalHeuristicAIAssistant)

    # Configure URLs + encrypted keys via Admin config API
    r_upd = adm.put(
        "/api/v1/admin/config/integrations",
        json=_base_integrations_payload(
            ocr_provider="http_ocr",
            ocr_api_base_url="https://ocr.vendor.test/extract",
            ocr_api_key="ocr-secret-key",
            ai_provider="gemini",
            gemini_api_key="gem-secret-key",
            pan_verification_provider="protean",
            pan_api_base_url="https://pan.protean.test/verify",
            pan_api_key="pan-secret-key",
            bank_verification_provider="razorpayx",
            bank_api_base_url="https://bank.rp.test/penny",
            bank_api_key="bank-secret-key",
            digilocker_provider="negd_oauth",
            digilocker_base_url="https://dl.negd.test/consent",
            digilocker_client_id="client-dl-1",
            digilocker_client_secret="dl-secret-key",
            face_match_provider="aws_rekognition",
            face_api_base_url="https://face.aws.test/compare",
            face_api_key="face-secret-key",
        ),
        headers=csrf(adm),
    )
    assert r_upd.status_code == 200
    cfg_out = r_upd.json()
    assert cfg_out["has_pan_api_key"] is True
    assert "pan-secret-key" not in r_upd.text
    assert "ocr-secret-key" not in r_upd.text

    def fake_vendor(method, url, headers=None, json=None, timeout=None):
        if "ocr.vendor.test" in url:
            return httpx.Response(
                200, json={"text": "INCOME TAX DEPARTMENT\nABCDE1234F\n01/01/1992", "confidence": 0.94}
            )
        if "pan.protean.test" in url:
            return httpx.Response(200, json={"verified": True, "reference_id": "PROT-881", "confidence": 0.99})
        if "bank.rp.test" in url:
            return httpx.Response(200, json={"verified": True, "utr": "UTR44019"})
        if "dl.negd.test" in url:
            return httpx.Response(200, json={"status": "VERIFIED", "request_id": "DL-992"})
        if "face.aws.test" in url:
            return httpx.Response(200, json={"verified": True, "similarity": 0.93, "reference_id": "FACE-221"})
        return httpx.Response(404)

    with patch("app.services.http_client.httpx.request", side_effect=fake_vendor), get_sessionmaker()() as db:
        assert isinstance(get_ai_assistant(db), GeminiAIAssistant)
        p_res = check_pan_verification_adapter("ABCDE1234F", full_name="Asha", db=db)
        b_res = check_bank_penny_drop_adapter("HDFC0000240", "Asha", db=db)
        d_res = check_digilocker_adapter(application_id="app-1", db=db)
        f_res = check_face_match_adapter(True, application_id="app-1", db=db)

        for r in (p_res, b_res, d_res, f_res):
            assert r.status == "PASSED"
            assert r.origin == "REAL_PROVIDER"
            assert r.is_simulated is False

        assert p_res.provider_reference == "PROT-881"
        assert b_res.provider_reference == "UTR44019"
        assert d_res.provider_reference == "DL-992"
        assert f_res.confidence == 0.93

        # HTTP OCR on small valid PNG bytes
        import cv2
        import numpy as np

        img = np.full((80, 160, 3), 255, dtype=np.uint8)
        ok, png_buf = cv2.imencode(".png", img)
        assert ok
        ocr_out = process_document_bytes("PAN_CARD", "image/png", png_buf.tobytes(), db=db)
        assert ocr_out.ocr_engine == "HTTP_OCR"
        assert ocr_out.extracted_fields.get("pan_number") == "ABCDE1234F"

    # Timeout -> UNAVAILABLE cleanly
    with (
        patch("app.services.http_client.httpx.request", side_effect=httpx.ReadTimeout("timeout")),
        get_sessionmaker()() as db,
    ):
        to_res = check_pan_verification_adapter("ABCDE1234F", db=db)
        assert to_res.status == "UNAVAILABLE"
        assert to_res.provider_reference is None


def test_signed_verification_webhooks_and_idempotency(make_client, mailbox):
    create_staff("ADMIN", "wh.admin@example.com", "Webhook Admin", region="ALL")
    adm = make_client()
    login(adm, "wh.admin@example.com")

    app_c = _verified_applicant(make_client, mailbox, email="wh.app@example.com", name="Webhook Applicant")
    app_id = app_c.post("/api/v1/applications", json={}, headers=csrf(app_c)).json()["id"]
    app_c.patch(
        f"/api/v1/applications/{app_id}", json=_complete_draft_payload(), headers=csrf(app_c)
    ).raise_for_status()

    # 1. Secret not configured -> 401
    raw = json.dumps({"event_id": "evt-0", "application_id": app_id, "status": "PASSED"}).encode("utf-8")
    r_no_sec = app_c.post(
        "/api/v1/webhooks/verification/pan", content=raw, headers={"X-PolicyNest-Signature": "sha256=deadbeef"}
    )
    assert r_no_sec.status_code == 401

    # Configure shared webhook HMAC secret
    secret = "wh-shared-secret-topsecret"
    adm.put(
        "/api/v1/admin/config/integrations",
        json=_base_integrations_payload(webhook_shared_secret=secret),
        headers=csrf(adm),
    ).raise_for_status()

    # 2. Bad HMAC signature -> 401 and logged REJECTED_SIGNATURE
    r_bad = app_c.post(
        "/api/v1/webhooks/verification/pan", content=raw, headers={"X-PolicyNest-Signature": "sha256=bad"}
    )
    assert r_bad.status_code == 401

    # 3. Valid HMAC -> creates VerificationCheck (REAL_PROVIDER) + Event + PROCESSED delivery
    valid_body = json.dumps(
        {
            "event_id": "pan-evt-1001",
            "application_id": app_id,
            "status": "VERIFIED",
            "provider_name": "protean",
            "provider_reference": "EXT-PAN-901",
            "confidence": 0.98,
        }
    ).encode("utf-8")
    r_ok = app_c.post(
        "/api/v1/webhooks/verification/pan",
        content=valid_body,
        headers={"X-PolicyNest-Signature": _sign(secret, valid_body)},
    )
    assert r_ok.status_code == 200
    assert r_ok.json()["processing_status"] == "PROCESSED"

    # 4. Duplicate event_id replay -> DUPLICATE_IGNORED
    r_dup = app_c.post(
        "/api/v1/webhooks/verification/pan",
        content=valid_body,
        headers={"X-PolicyNest-Signature": _sign(secret, valid_body)},
    )
    assert r_dup.status_code == 200
    assert r_dup.json()["processing_status"] == "DUPLICATE_IGNORED"

    with get_sessionmaker()() as db:
        chk = db.scalar(
            select(VerificationCheck).where(
                VerificationCheck.application_id == uuid.UUID(app_id),
                VerificationCheck.check_type == "EXTERNAL_PAN",
            )
        )
        assert chk is not None
        assert chk.status == "PASSED"
        assert chk.origin == "REAL_PROVIDER"
        assert chk.provider_reference == "EXT-PAN-901"
        assert chk.is_simulated is False

        ev = db.scalar(
            select(ApplicationEvent).where(
                ApplicationEvent.application_id == uuid.UUID(app_id),
                ApplicationEvent.event_type == "VENDOR_WEBHOOK_RECEIVED",
            )
        )
        assert ev is not None

        deliveries = db.scalars(select(WebhookDelivery).where(WebhookDelivery.source == "pan")).all()
        assert any(d.processing_status == "REJECTED_SIGNATURE" and d.signature_valid is False for d in deliveries)
        assert sum(1 for d in deliveries if d.external_event_id == "pan-evt-1001") == 1


def test_lms_webhook_records_delivery_and_admin_probe_monitor(make_client, mailbox):
    create_staff("ADMIN", "mon.admin@example.com", "Monitor Admin", region="ALL")
    adm = make_client()
    login(adm, "mon.admin@example.com")

    adm.put(
        "/api/v1/admin/config/lms",
        json={
            "lms_provider": "sandbox",
            "lms_api_base_url": None,
            "lms_course_code": "IRDAI-POSP-15H",
            "lms_required_hours": 15.0,
            "lms_passing_score_pct": 50.0,
            "lms_timeout_seconds": 10,
            "lms_exam_cooldown_hours": 24,
            "lms_certificate_validity_years": 5,
            "lms_sync_retry_base_seconds": 60,
            "lms_sync_max_attempts": 3,
            "lms_api_key": None,
            "clear_api_key": False,
            "lms_webhook_secret": "lms-wh-secret",
            "clear_webhook_secret": False,
        },
        headers=csrf(adm),
    ).raise_for_status()

    app_c, app_id = _create_kyc_approved_app(make_client, mailbox)
    r_enroll = app_c.post(f"/api/v1/applications/{app_id}/training/enroll", headers=csrf(app_c))
    r_enroll.raise_for_status()
    ext_id = r_enroll.json()["external_enrollment_id"]

    lms_payload = json.dumps(
        {
            "event_id": "lms-evt-55",
            "external_enrollment_id": ext_id,
            "enrollment_status": "COMPLETED",
            "completed_hours": 15.0,
            "exam_status": "PASSED",
            "exam_score_pct": 80.0,
            "certificate_number": "PN-CERT-8855",
        }
    ).encode("utf-8")
    r_lms_wh = app_c.post(
        "/api/v1/training/webhooks/lms",
        content=lms_payload,
        headers={
            "Content-Type": "application/json",
            "X-LMS-Signature": "sha256=" + hmac.new(b"lms-wh-secret", lms_payload, hashlib.sha256).hexdigest(),
        },
    )
    assert r_lms_wh.status_code == 200

    # Mock external HTTP probes so offline unit suite doesn't rely on live internet
    with patch("app.services.integration_health.request_json_with_retry") as mock_http:
        mock_http.return_value = type(
            "R",
            (),
            {
                "ok": True,
                "status_code": 200,
                "data": {},
                "attempts": 1,
                "latency_ms": 12,
                "error_code": None,
                "error_message": None,
            },
        )()
        r_probe = adm.post("/api/v1/admin/integrations/probe", headers=csrf(adm))
    assert r_probe.status_code == 200
    probes = r_probe.json()
    assert any(p["adapter_key"] == "database" and p["status"] == "CONFIGURED" for p in probes)
    assert any(p["adapter_key"] == "sms" for p in probes)
    assert any(p["adapter_key"] == "webhooks" for p in probes)

    r_mon = adm.get("/api/v1/admin/integrations/monitor")
    assert r_mon.status_code == 200
    mon = r_mon.json()
    assert len(mon["probes"]) >= 1
    assert any(w["source"] == "lms" and w["processing_status"] == "PROCESSED" for w in mon["webhook_deliveries"])

    # Verify audit log does not store plaintext webhook secrets
    with get_sessionmaker()() as db:
        audits = db.scalars(select(AuditLog)).all()
        for entry in audits:
            assert "lms-wh-secret" not in json.dumps(entry.details or {})
        cfg_row = db.get(SystemConfig, "lms")
        assert cfg_row is not None
