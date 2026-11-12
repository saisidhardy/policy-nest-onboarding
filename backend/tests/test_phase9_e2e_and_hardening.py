import hashlib
import hmac
import uuid

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.models import Application, ApplicationEvent, AuditLog, TrainingRecord
from app.services.storage import get_storage, set_storage_override
from tests.conftest import create_staff, csrf, login
from tests.test_phase4_rules import _create_full_draft_with_docs


def test_full_posp_lifecycle_registration_to_certification(make_client, mailbox):
    """End-to-end validation from applicant registration through KYC approval to POSP certification."""
    create_staff("ADMIN", "p9.admin@example.com", name="System Admin", region="ALL", clearance=3)
    create_staff("REVIEWER", "p9.rev@example.com", name="South Reviewer", region="SOUTH", clearance=2)
    create_staff("SENIOR_REVIEWER", "p9.sr@example.com", name="South Senior", region="SOUTH", clearance=3)

    app_c = make_client()
    app_id, sub_data = _create_full_draft_with_docs(
        app_c,
        mailbox,
        email="p9.e2e@example.com",
        full_name="Asha Verma",
        pan="ABCPV9901K",
        pan_card_name="Asha Verma",
        aadhaar_name="Rohan Deshmukh",  # Triggers HUMAN_REVIEW -> full reviewer decision workflow
    )
    assert sub_data["status"] == "SUBMITTED"

    # 1. Run deterministic PS-01 evaluation -> transitions application to IN_REVIEW
    r_eval = app_c.post(f"/api/v1/applications/{app_id}/evaluate", headers=csrf(app_c))
    assert r_eval.status_code == 200, r_eval.text
    assert r_eval.json()["outcome"] == "HUMAN_REVIEW"
    assert r_eval.json()["recommended_status"] == "IN_REVIEW"

    # 2. Reviewer claims case, reviews extraction & verification results, escalates NAME_MISMATCH to Senior Reviewer
    rev_c = make_client()
    assert login(rev_c, "p9.rev@example.com").status_code == 200
    r_claim = rev_c.post(f"/api/v1/review/applications/{app_id}/claim", json={"action": "claim"}, headers=csrf(rev_c))
    assert r_claim.status_code == 200

    r_esc = rev_c.post(
        f"/api/v1/applications/{app_id}/decide",
        json={
            "decision": "ESCALATE",
            "reason_codes": ["NAME_MISMATCH"],
            "reason_text": "Escalating Tier 7 name difference for senior identity verification.",
        },
        headers=csrf(rev_c),
    )
    assert r_esc.status_code == 200

    # 3. Senior Reviewer confirms identity & approves KYC -> triggers training eligibility
    sr_c = make_client()
    assert login(sr_c, "p9.sr@example.com").status_code == 200
    r_apr = sr_c.post(
        f"/api/v1/applications/{app_id}/decide",
        json={
            "decision": "APPROVE",
            "reason_codes": ["NAME_MISMATCH"],
            "reason_text": "Confirmed supporting gazette document; approved KYC.",
        },
        headers=csrf(sr_c),
    )
    assert r_apr.status_code == 200
    assert r_apr.json()["new_status"] == "KYC_APPROVED"

    # 4. Admin enables Sandbox LMS via DB configuration console
    adm_c = make_client()
    assert login(adm_c, "p9.admin@example.com").status_code == 200
    adm_c.put(
        "/api/v1/admin/config/lms",
        json={
            "lms_provider": "sandbox",
            "lms_api_base_url": None,
            "lms_course_code": "IRDAI-POSP-15H",
            "lms_required_hours": 15.0,
            "lms_passing_score_pct": 50.0,
            "lms_timeout_seconds": 8,
            "lms_exam_cooldown_hours": 24,
            "lms_certificate_validity_years": 3,
            "lms_sync_retry_base_seconds": 300,
            "lms_sync_max_attempts": 5,
            "lms_api_key": None,
            "clear_api_key": False,
            "lms_webhook_secret": None,
            "clear_webhook_secret": False,
        },
        headers=csrf(adm_c),
    ).raise_for_status()

    # 5. Applicant enrolls, completes 15h IRDAI course, passes exam, and receives POSP certificate
    r_tr0 = app_c.get(f"/api/v1/applications/{app_id}/training")
    assert r_tr0.status_code == 200
    assert r_tr0.json()["eligibility_status"] == "ELIGIBLE"

    app_c.post(f"/api/v1/applications/{app_id}/training/enroll", headers=csrf(app_c)).raise_for_status()
    app_c.post(
        f"/api/v1/applications/{app_id}/training/sync",
        json={"sandbox_action": "COMPLETE_15H"},
        headers=csrf(app_c),
    ).raise_for_status()
    r_pass = app_c.post(
        f"/api/v1/applications/{app_id}/training/sync",
        json={"sandbox_action": "PASS_EXAM"},
        headers=csrf(app_c),
    )
    assert r_pass.status_code == 200
    cert = r_pass.json()
    assert cert["certification_status"] == "CERTIFIED"
    assert cert["application_status"] == "CERTIFIED"
    assert cert["certificate_number"].startswith("SBX-CERT-")

    # 6. Verify final PostgreSQL state, history, and audit log completeness
    with get_sessionmaker()() as db:
        app_row = db.get(Application, uuid.UUID(app_id))
        assert app_row is not None and app_row.status == "CERTIFIED"
        tr_row = db.scalar(select(TrainingRecord).where(TrainingRecord.application_id == uuid.UUID(app_id)))
        assert tr_row is not None and tr_row.certificate_number == cert["certificate_number"]
        events = [
            e.event_type
            for e in db.scalars(select(ApplicationEvent).where(ApplicationEvent.application_id == app_row.id)).all()
        ]
        assert "APPLICATION_SUBMITTED" in events
        assert "REVIEWER_APPROVE" in events
        assert "POSP_CERTIFIED" in events
        audits = [a.action for a in db.scalars(select(AuditLog)).all()]
        assert "application.submitted" in audits
        assert "application.decided" in audits
        assert "training.enroll" in audits
        assert "training.status_sync" in audits


def test_error_handling_security_headers_and_storage_boundaries(client, mailbox, monkeypatch):
    """Verify structured error envelopes, security headers, health/OpenAPI routes, and unconfigured S3 honesty."""
    create_staff("ADMIN", "p9.sec@example.com", name="Security Admin", region="ALL", clearance=3)

    # Health & OpenAPI contract
    r_live = client.get("/health")
    assert r_live.status_code == 200
    assert r_live.headers["x-content-type-options"] == "nosniff"
    assert r_live.headers["x-frame-options"] == "DENY"
    assert "referrer-policy" in r_live.headers

    r_ready = client.get("/health/ready")
    assert r_ready.status_code == 200
    assert r_ready.json()["database"]["migration"] == "0008_phase8_integrations"

    r_spec = client.get("/api/openapi.json")
    assert r_spec.status_code == 200
    paths = r_spec.json()["paths"]
    assert "/api/v1/webhooks/verification/{source}" in paths
    assert "/api/v1/admin/integrations/probe" in paths
    assert "/api/v1/admin/integrations/monitor" in paths

    assert login(client, "p9.sec@example.com").status_code == 200

    # Malformed UUID -> clean 422 JSON without traceback
    r_bad_uuid = client.get("/api/v1/applications/not-a-uuid")
    assert r_bad_uuid.status_code == 422
    assert "Traceback" not in r_bad_uuid.text

    # Non-existent UUID -> structured 404
    r_not_found = client.get(f"/api/v1/applications/{uuid.uuid4()}")
    assert r_not_found.status_code == 404
    assert r_not_found.json()["error"]["code"] == "APPLICATION_NOT_FOUND"

    # Malformed JSON on signed webhook -> 400 INVALID_WEBHOOK_JSON
    client.put(
        "/api/v1/admin/config/integrations",
        json={
            "ocr_provider": "local_tesseract",
            "ai_provider": "local_heuristic",
            "gemini_model": "gemini-3.8-flash",
            "ifsc_lookup_enabled": False,
            "pan_verification_provider": "not_configured",
            "bank_verification_provider": "not_configured",
            "digilocker_provider": "not_configured",
            "face_match_provider": "not_configured",
            "webhook_shared_secret": "err-test-secret",
        },
        headers=csrf(client),
    ).raise_for_status()

    bad_json = b"{not valid json"
    sig = "sha256=" + hmac.new(b"err-test-secret", bad_json, hashlib.sha256).hexdigest()
    r_bad_wh = client.post(
        "/api/v1/webhooks/verification/pan", content=bad_json, headers={"X-PolicyNest-Signature": sig}
    )
    assert r_bad_wh.status_code == 400
    assert r_bad_wh.json()["error"]["code"] == "INVALID_WEBHOOK_JSON"

    # S3 storage mode without bucket credentials fails fast rather than silently faking persistence
    monkeypatch.setenv("STORAGE_PROVIDER", "s3")
    monkeypatch.setenv("S3_BUCKET", "")
    get_settings.cache_clear()
    set_storage_override(None)
    try:
        with pytest.raises(RuntimeError, match="S3_BUCKET"):
            get_storage()
    finally:
        monkeypatch.delenv("STORAGE_PROVIDER", raising=False)
        monkeypatch.delenv("S3_BUCKET", raising=False)
        get_settings.cache_clear()
        set_storage_override(None)
