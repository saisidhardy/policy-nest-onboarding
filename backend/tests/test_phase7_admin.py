import uuid

from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.models import Application, AuditLog, SystemConfig
from app.models.base import utcnow
from tests.conftest import create_staff, csrf, login
from tests.test_applications import _complete_draft_payload, _verified_applicant


def _create_submitted_app(make_client, mailbox, email: str, name: str, region: str = "SOUTH") -> tuple:
    c = _verified_applicant(make_client, mailbox, email=email, name=name)
    app_id = c.post("/api/v1/applications", json={}, headers=csrf(c)).json()["id"]
    payload = _complete_draft_payload()
    payload["region"] = region
    c.patch(f"/api/v1/applications/{app_id}", json=payload, headers=csrf(c)).raise_for_status()
    with get_sessionmaker()() as db:
        row = db.get(Application, uuid.UUID(app_id))
        row.status = "IN_REVIEW"
        db.commit()
    return c, app_id


def test_admin_dashboard_and_permissions_enforced(make_client, mailbox):
    create_staff("ADMIN", "ops.admin@example.com", "Ops Admin", region="ALL")
    create_staff("REVIEWER", "ops.rev@example.com", "Ops Reviewer", region="SOUTH")
    _create_submitted_app(make_client, mailbox, "app.dash@example.com", "Ramesh Rao", region="SOUTH")

    rev_c = make_client()
    login(rev_c, "ops.rev@example.com")
    # Reviewer cannot access admin dashboard or config
    assert rev_c.get("/api/v1/admin/dashboard").status_code == 403
    assert rev_c.get("/api/v1/admin/config").status_code == 403

    adm_c = make_client()
    login(adm_c, "ops.admin@example.com")
    r_dash = adm_c.get("/api/v1/admin/dashboard")
    assert r_dash.status_code == 200
    dash = r_dash.json()
    assert dash["total_applications"] == 1
    assert dash["applications_by_status"]["IN_REVIEW"] == 1
    assert dash["reviewer_count"] == 1
    assert dash["senior_reviewer_count"] == 0
    assert any(it["key"] == "lms" for it in dash["integrations"])


def test_reviewer_workload_application_assign_and_separation_of_duties(make_client, mailbox):
    create_staff("ADMIN", "adm.assign@example.com", "Assign Admin", region="ALL")
    rev1_id = create_staff("REVIEWER", "rev.one@example.com", "Reviewer One", region="SOUTH")
    rev2_id = create_staff("REVIEWER", "rev.two@example.com", "Reviewer Two", region="SOUTH")
    sen_id = create_staff("SENIOR_REVIEWER", "sen.one@example.com", "Senior Reviewer", region="ALL")

    _, app_id = _create_submitted_app(make_client, mailbox, "app.assign@example.com", "Meena Iyer", region="SOUTH")

    adm_c = make_client()
    login(adm_c, "adm.assign@example.com")

    # Admin global search & filter
    r_apps = adm_c.get("/api/v1/admin/applications", params={"q": "Meena", "unassigned_only": "true"})
    assert r_apps.status_code == 200
    assert r_apps.json()["total"] == 1
    assert r_apps.json()["items"][0]["id"] == app_id

    # Admin assigns Reviewer One
    r_assign = adm_c.post(
        f"/api/v1/admin/applications/{app_id}/assign",
        json={"reviewer_id": str(rev1_id), "reason": "Balancing South region review queue"},
        headers=csrf(adm_c),
    )
    assert r_assign.status_code == 200
    assert r_assign.json()["assigned_reviewer_id"] == str(rev1_id)

    # Reviewer workload shows 1 active assigned case on Reviewer One
    workloads = {row["id"]: row for row in adm_c.get("/api/v1/admin/reviewers").json()}
    assert workloads[str(rev1_id)]["active_assigned_count"] == 1
    assert workloads[str(rev2_id)]["active_assigned_count"] == 0

    # Bulk reassign workload from Reviewer One to Reviewer Two
    r_reassign = adm_c.post(
        f"/api/v1/admin/reviewers/{rev1_id}/reassign-workload",
        json={"target_reviewer_id": str(rev2_id), "reason": "Reviewer One scheduled leave"},
        headers=csrf(adm_c),
    )
    assert r_reassign.status_code == 200
    assert r_reassign.json()["reassigned_count"] == 1

    workloads_after = {row["id"]: row for row in adm_c.get("/api/v1/admin/reviewers").json()}
    assert workloads_after[str(rev1_id)]["active_assigned_count"] == 0
    assert workloads_after[str(rev2_id)]["active_assigned_count"] == 1

    # Escalated case cannot be assigned to standard REVIEWER
    with get_sessionmaker()() as db:
        row = db.get(Application, uuid.UUID(app_id))
        row.escalated_at = utcnow()
        db.commit()

    r_esc_fail = adm_c.post(
        f"/api/v1/admin/reviewers/{rev2_id}/reassign-workload",
        json={"target_reviewer_id": str(rev1_id), "reason": "Should fail for escalated case"},
        headers=csrf(adm_c),
    )
    assert r_esc_fail.status_code == 400
    assert r_esc_fail.json()["error"]["code"] == "SENIOR_REVIEWER_REQUIRED"

    # Assigning to SENIOR_REVIEWER succeeds
    r_esc_ok = adm_c.post(
        f"/api/v1/admin/reviewers/{rev2_id}/reassign-workload",
        json={"target_reviewer_id": str(sen_id), "reason": "Escalated case routed to Senior Reviewer"},
        headers=csrf(adm_c),
    )
    assert r_esc_ok.status_code == 200
    assert r_esc_ok.json()["reassigned_count"] == 1

    # Separation of Duties: ADMIN still forbidden from deciding an application
    r_decide = adm_c.post(
        f"/api/v1/applications/{app_id}/decide",
        json={"decision": "APPROVE", "reason_text": "Attempt by admin"},
        headers=csrf(adm_c),
    )
    assert r_decide.status_code == 403


def test_role_permissions_customization_and_guards(make_client):
    create_staff("ADMIN", "adm.rbac@example.com", "RBAC Admin", region="ALL")
    adm_c = make_client()
    login(adm_c, "adm.rbac@example.com")

    # APPLICANT cannot be edited
    r_app_edit = adm_c.put(
        "/api/v1/admin/roles/APPLICANT/permissions",
        json={"permission_codes": ["profile:read"], "reason": "Test protected applicant role"},
        headers=csrf(adm_c),
    )
    assert r_app_edit.status_code == 400
    assert r_app_edit.json()["error"]["code"] == "ROLE_PROTECTED"

    # Separation of Duties: ADMIN cannot grant itself application:decide
    admin_role = next(r for r in adm_c.get("/api/v1/admin/roles").json()["roles"] if r["code"] == "ADMIN")
    admin_codes = list(admin_role["permissions"])
    r_sod = adm_c.put(
        "/api/v1/admin/roles/ADMIN/permissions",
        json={"permission_codes": admin_codes + ["application:decide"], "reason": "Test SoD guard"},
        headers=csrf(adm_c),
    )
    assert r_sod.status_code == 400
    assert r_sod.json()["error"]["code"] == "SEPARATION_OF_DUTIES"

    # Lockout guard: ADMIN cannot strip users:manage
    r_lock = adm_c.put(
        "/api/v1/admin/roles/ADMIN/permissions",
        json={
            "permission_codes": [c for c in admin_codes if c != "users:manage"],
            "reason": "Test lockout guard",
        },
        headers=csrf(adm_c),
    )
    assert r_lock.status_code == 400
    assert r_lock.json()["error"]["code"] == "REQUIRED_ADMIN_PERMISSION"

    # REVIEWER role can be customized cleanly and restored
    rev_role = next(r for r in adm_c.get("/api/v1/admin/roles").json()["roles"] if r["code"] == "REVIEWER")
    orig_codes = list(rev_role["permissions"])
    assert "application:escalate" in orig_codes
    try:
        r_upd = adm_c.put(
            "/api/v1/admin/roles/REVIEWER/permissions",
            json={
                "permission_codes": [c for c in orig_codes if c != "application:escalate"],
                "reason": "Temporarily restrict escalation permission",
            },
            headers=csrf(adm_c),
        )
        assert r_upd.status_code == 200
        assert "application:escalate" not in r_upd.json()["permissions"]
    finally:
        adm_c.put(
            "/api/v1/admin/roles/REVIEWER/permissions",
            json={"permission_codes": orig_codes, "reason": "Restore seeded permissions"},
            headers=csrf(adm_c),
        ).raise_for_status()


def test_db_config_encryption_masking_health_and_reset(make_client, monkeypatch):
    create_staff("ADMIN", "adm.cfg@example.com", "Config Admin", region="ALL")
    adm_c = make_client()
    login(adm_c, "adm.cfg@example.com")

    raw_api_key = "super-secret-lms-key-9876"
    raw_wh_secret = "whsec_abcdef123456"

    # Save LMS config into PostgreSQL with encrypted secrets
    r_lms = adm_c.put(
        "/api/v1/admin/config/lms",
        json={
            "lms_provider": "sandbox",
            "lms_api_base_url": None,
            "lms_course_code": "IRDAI-POSP-V2",
            "lms_required_hours": 15.0,
            "lms_passing_score_pct": 60.0,
            "lms_timeout_seconds": 10,
            "lms_exam_cooldown_hours": 12,
            "lms_certificate_validity_years": 3,
            "lms_sync_retry_base_seconds": 120,
            "lms_sync_max_attempts": 4,
            "lms_api_key": raw_api_key,
            "clear_api_key": False,
            "lms_webhook_secret": raw_wh_secret,
            "clear_webhook_secret": False,
        },
        headers=csrf(adm_c),
    )
    assert r_lms.status_code == 200
    lms_out = r_lms.json()
    assert lms_out["source"] == "database"
    assert lms_out["lms_provider"] == "sandbox"
    assert lms_out["has_api_key"] is True
    assert lms_out["api_key_hint"] == "••••9876"
    assert raw_api_key not in str(lms_out)
    assert raw_wh_secret not in str(lms_out)

    # DB row stores Fernet ciphertext (never plaintext) and AuditLog never logs raw secrets
    with get_sessionmaker()() as db:
        cfg_row = db.get(SystemConfig, "lms")
        assert cfg_row is not None
        assert raw_api_key not in str(cfg_row.secrets_encrypted)
        assert raw_wh_secret not in str(cfg_row.secrets_encrypted)
        last_audit = db.query(AuditLog).filter(AuditLog.action == "admin.config.lms_updated").first()
        assert last_audit is not None
        assert raw_api_key not in str(last_audit.details)
        assert raw_wh_secret not in str(last_audit.details)

    # Health endpoint immediately reflects DB override (LMS = SANDBOX)
    health_integrations = {row["key"]: row for row in adm_c.get("/api/v1/admin/system/health").json()["integrations"]}
    assert health_integrations["lms"]["status"] == "CONFIGURED"
    assert health_integrations["lms"]["mode"] == "SANDBOX"

    # Production guard rejects sandbox providers when APP_ENV=production
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    try:
        r_prod = adm_c.put(
            "/api/v1/admin/config/integrations",
            json={
                "ocr_provider": "local_tesseract",
                "ai_provider": "local_heuristic",
                "gemini_model": "gemini-3.8-flash",
                "ifsc_lookup_enabled": False,
                "pan_verification_provider": "sandbox",
                "bank_verification_provider": "not_configured",
                "digilocker_provider": "not_configured",
                "face_match_provider": "not_configured",
            },
            headers=csrf(adm_c),
        )
        assert r_prod.status_code == 400
        assert r_prod.json()["error"]["code"] == "SANDBOX_FORBIDDEN_IN_PROD"
    finally:
        monkeypatch.setenv("APP_ENV", "test")
        get_settings.cache_clear()

    # Reset LMS config section reverts source to environment defaults
    r_reset = adm_c.post("/api/v1/admin/config/reset/lms", headers=csrf(adm_c))
    assert r_reset.status_code == 200
    assert r_reset.json()["lms"]["source"] == "environment"
