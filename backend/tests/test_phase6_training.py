import hashlib
import hmac
import json
import uuid
from types import SimpleNamespace

from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.models import Application
from app.services import training as training_service
from tests.conftest import create_staff, csrf, login
from tests.test_applications import _complete_draft_payload, _verified_applicant


def _create_kyc_approved_app(make_client, mailbox, email: str = "train.app@example.com"):
    c = _verified_applicant(make_client, mailbox, email=email, name="Kavita Nair")
    app_id = c.post("/api/v1/applications", json={}, headers=csrf(c)).json()["id"]
    c.patch(f"/api/v1/applications/{app_id}", json=_complete_draft_payload(), headers=csrf(c)).raise_for_status()

    with get_sessionmaker()() as db:
        app_row = db.get(Application, uuid.UUID(app_id))
        app_row.status = "KYC_APPROVED"
        app_row.region = "SOUTH"
        training_service.sync_eligibility_on_kyc_approval(db, app_row)
        db.commit()
    return c, app_id


def test_training_eligibility_and_unconfigured_lms_honesty(make_client, mailbox, monkeypatch):
    c = _verified_applicant(make_client, mailbox, email="elig.app@example.com", name="Suresh Kumar")
    draft_id = c.post("/api/v1/applications", json={}, headers=csrf(c)).json()["id"]

    # Draft application is ineligible before KYC approval
    r_draft = c.get(f"/api/v1/applications/{draft_id}/training")
    assert r_draft.status_code == 200
    assert r_draft.json()["eligibility_status"] == "NOT_ELIGIBLE"

    r_enroll_early = c.post(f"/api/v1/applications/{draft_id}/training/enroll", headers=csrf(c))
    assert r_enroll_early.status_code == 409
    assert r_enroll_early.json()["error"]["code"] == "INELIGIBLE_FOR_TRAINING"

    monkeypatch.setenv("LMS_PROVIDER", "not_configured")
    get_settings.cache_clear()
    try:
        with get_sessionmaker()() as db:
            app_row = db.get(Application, uuid.UUID(draft_id))
            app_row.status = "KYC_APPROVED"
            training_service.sync_eligibility_on_kyc_approval(db, app_row)
            db.commit()

        r_elig = c.get(f"/api/v1/applications/{draft_id}/training")
        assert r_elig.status_code == 200
        assert r_elig.json()["eligibility_status"] == "ELIGIBLE"
        assert r_elig.json()["adapter_status"]["status"] == "NOT_CONFIGURED"

        # Attempting enroll when unconfigured records honest failure without fabricating enrollment
        r_fail = c.post(f"/api/v1/applications/{draft_id}/training/enroll", headers=csrf(c))
        assert r_fail.status_code == 200
        body = r_fail.json()
        assert body["sync_status"] == "NOT_CONFIGURED"
        assert body["last_error_code"] == "LMS_NOT_CONFIGURED"
        assert body["external_enrollment_id"] is None
        assert body["enrollment_status"] == "NOT_ENROLLED"
        assert body["application_status"] == "KYC_APPROVED"
        assert body["sync_logs"][0]["outcome"] == "UNCONFIGURED"
    finally:
        monkeypatch.delenv("LMS_PROVIDER", raising=False)
        get_settings.cache_clear()


def test_lms_sandbox_lifecycle_cooldown_and_retry_recovery(make_client, mailbox, monkeypatch):
    monkeypatch.setenv("LMS_PROVIDER", "sandbox")
    get_settings.cache_clear()
    try:
        c, app_id = _create_kyc_approved_app(make_client, mailbox, "sbx.train@example.com")

        # IDOR protection check against another applicant
        other = _verified_applicant(make_client, mailbox, email="other.train@example.com", name="Other User")
        assert other.get(f"/api/v1/applications/{app_id}/training").status_code == 403

        # Enroll in LMS -> application becomes TRAINING_IN_PROGRESS
        en = c.post(f"/api/v1/applications/{app_id}/training/enroll", headers=csrf(c))
        assert en.status_code == 200
        en_body = en.json()
        assert en_body["is_simulated"] is True
        assert en_body["enrollment_status"] == "ENROLLED"
        assert en_body["application_status"] == "TRAINING_IN_PROGRESS"
        assert en_body["external_enrollment_id"].startswith("SBX-")
        assert len(en_body["module_progress"]) == 6

        # Advance 7.5 hours and 15.0 hours
        mid = c.post(
            f"/api/v1/applications/{app_id}/training/sync",
            json={"sandbox_action": "ADVANCE_7_5H"},
            headers=csrf(c),
        ).json()
        assert mid["completed_hours"] == 7.5
        assert mid["progress_pct"] == 50.0
        assert mid["enrollment_status"] == "IN_PROGRESS"

        done = c.post(
            f"/api/v1/applications/{app_id}/training/sync",
            json={"sandbox_action": "COMPLETE_15H"},
            headers=csrf(c),
        ).json()
        assert done["completed_hours"] == 15.0
        assert done["progress_pct"] == 100.0
        assert done["enrollment_status"] == "COMPLETED"
        assert done["exam_status"] == "ELIGIBLE"

        # Fail exam -> 24h cooldown enforced, not certified
        fail_ex = c.post(
            f"/api/v1/applications/{app_id}/training/sync",
            json={"sandbox_action": "FAIL_EXAM"},
            headers=csrf(c),
        ).json()
        assert fail_ex["exam_status"] == "COOLDOWN"
        assert fail_ex["exam_score_pct"] == 42.0
        assert fail_ex["next_exam_eligible_at"] is not None
        assert fail_ex["certification_status"] == "NOT_CERTIFIED"

        # Simulate transient HTTP 503 sync error -> RETRY_PENDING with backoff
        err = c.post(
            f"/api/v1/applications/{app_id}/training/sync",
            json={"sandbox_action": "SIMULATE_SYNC_ERROR"},
            headers=csrf(c),
        ).json()
        assert err["sync_status"] == "RETRY_PENDING"
        assert err["sync_attempts"] == 1
        assert err["next_retry_at"] is not None
        assert err["last_error_code"] == "LMS_TEMPORARY_UNAVAILABLE"

        # Manual retry recovers cleanly
        rec = c.post(f"/api/v1/applications/{app_id}/training/retry", headers=csrf(c)).json()
        assert rec["sync_status"] == "SYNCED"
        assert rec["sync_attempts"] == 0
        assert rec["last_error_code"] is None

        # Pass exam -> POSP CERTIFIED
        passed = c.post(
            f"/api/v1/applications/{app_id}/training/sync",
            json={"sandbox_action": "PASS_EXAM"},
            headers=csrf(c),
        ).json()
        assert passed["exam_status"] == "PASSED"
        assert passed["certification_status"] == "CERTIFIED"
        assert passed["certificate_number"].startswith("SBX-CERT-")
        assert passed["application_status"] == "CERTIFIED"
    finally:
        monkeypatch.delenv("LMS_PROVIDER", raising=False)
        get_settings.cache_clear()


def test_http_api_adapter_batch_retry_and_signed_webhook_irdai_guard(make_client, mailbox, monkeypatch):
    create_staff("ADMIN", "train.admin@example.com", "Admin User", region="ALL", clearance=3)
    admin_c = make_client()
    assert login(admin_c, "train.admin@example.com").status_code == 200

    monkeypatch.setenv("LMS_PROVIDER", "http_api")
    monkeypatch.setenv("LMS_API_BASE_URL", "https://lms.example.internal/api")
    monkeypatch.setenv("LMS_API_KEY", "secret-token")
    monkeypatch.setenv("LMS_WEBHOOK_SECRET", "whsec_test_policynest_64")
    get_settings.cache_clear()
    try:
        c, app_id = _create_kyc_approved_app(make_client, mailbox, "http.train@example.com")

        calls = {"post": 0}

        def fake_post(url, json=None, headers=None, timeout=None):
            calls["post"] += 1
            if calls["post"] == 1:
                return SimpleNamespace(status_code=502, json=lambda: {"error": "bad gateway"})
            return SimpleNamespace(
                status_code=201,
                json=lambda: {
                    "external_enrollment_id": "LMS-EXT-991",
                    "launch_url": "https://lms.example.internal/learn/LMS-EXT-991",
                    "enrollment_status": "ENROLLED",
                    "completed_hours": 0.0,
                },
            )

        monkeypatch.setattr("app.services.lms_adapter.httpx.post", fake_post)

        r1 = c.post(f"/api/v1/applications/{app_id}/training/enroll", headers=csrf(c)).json()
        assert r1["sync_status"] == "RETRY_PENDING"
        assert r1["last_error_code"] == "LMS_HTTP_502"

        # Admin sees overview and runs batch retry
        ov = admin_c.get("/api/v1/training/overview").json()
        assert ov["adapter_status"]["mode"] == "LIVE"
        assert ov["sync_retry_pending_count"] == 1

        batch = admin_c.post("/api/v1/training/retry-due", headers=csrf(admin_c)).json()
        assert batch["attempted"] == 1 and batch["succeeded"] == 1

        # Health endpoint exposes live LMS integration status
        health = admin_c.get("/api/v1/admin/system/health").json()
        lms_int = next(i for i in health["integrations"] if i["key"] == "lms")
        assert lms_int["status"] == "CONFIGURED" and lms_int["mode"] == "LIVE"

        # Invalid webhook signature rejected
        bad_wh = c.post(
            "/api/v1/training/webhooks/lms",
            content=b'{"external_enrollment_id":"LMS-EXT-991"}',
            headers={"Content-Type": "application/json", "X-LMS-Signature": "sha256=deadbeef"},
        )
        assert bad_wh.status_code == 401

        # Signed webhook attempting to certify with only 10.0 hours (< 15.0 IRDAI floor) is blocked!
        early_payload = json.dumps(
            {
                "event_id": "evt-1",
                "external_enrollment_id": "LMS-EXT-991",
                "enrollment_status": "IN_PROGRESS",
                "completed_hours": 10.0,
                "exam_status": "PASSED",
                "exam_score_pct": 80.0,
                "certificate_number": "PN-PREMATURE",
            }
        ).encode("utf-8")
        sig1 = "sha256=" + hmac.new(b"whsec_test_policynest_64", early_payload, hashlib.sha256).hexdigest()
        r_guard = c.post(
            "/api/v1/training/webhooks/lms",
            content=early_payload,
            headers={"Content-Type": "application/json", "X-LMS-Signature": sig1},
        )
        assert r_guard.status_code == 200
        assert r_guard.json()["last_error_code"] == "IRDAI_CERTIFICATION_GUARD_FAILED"
        assert r_guard.json()["certification_status"] == "NOT_CERTIFIED"

        # Signed webhook with 15.0h + passing exam certifies the POSP cleanly
        valid_payload = json.dumps(
            {
                "event_id": "evt-2",
                "external_enrollment_id": "LMS-EXT-991",
                "enrollment_status": "COMPLETED",
                "completed_hours": 15.0,
                "exam_status": "PASSED",
                "exam_score_pct": 78.0,
                "exam_attempts": 1,
                "certificate_number": "PN-REAL-2601",
            }
        ).encode("utf-8")
        sig2 = "sha256=" + hmac.new(b"whsec_test_policynest_64", valid_payload, hashlib.sha256).hexdigest()
        r_cert = c.post(
            "/api/v1/training/webhooks/lms",
            content=valid_payload,
            headers={"Content-Type": "application/json", "X-LMS-Signature": sig2},
        )
        assert r_cert.status_code == 200
        cert_body = r_cert.json()
        assert cert_body["certification_status"] == "CERTIFIED"
        assert cert_body["certificate_number"] == "PN-REAL-2601"
        assert cert_body["application_status"] == "CERTIFIED"
        assert cert_body["is_simulated"] is False
    finally:
        for k in ("LMS_PROVIDER", "LMS_API_BASE_URL", "LMS_API_KEY", "LMS_WEBHOOK_SECRET"):
            monkeypatch.delenv(k, raising=False)
        get_settings.cache_clear()
