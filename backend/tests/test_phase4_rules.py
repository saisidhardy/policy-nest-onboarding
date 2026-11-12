from __future__ import annotations

import uuid
from datetime import date, timedelta
from pathlib import Path

import cv2
import numpy as np
from sqlalchemy import select

from app.core.db import get_sessionmaker
from app.models import Application, ApplicationEvent, AuditLog, RuleExecution
from tests.conftest import create_staff, csrf, login, register, verify_user_email

SPECIMEN_DIR = (
    Path(__file__).resolve().parents[2] / "docs" / "source_materials" / "05_SPECIMEN_DOCUMENTS" / "sample_specimens"
)


def _render_card(lines: list[str], *, width: int = 1100, height: int = 680) -> bytes:
    canvas = np.full((height, width, 3), 255, dtype=np.uint8)
    y = 95
    for line in lines:
        cv2.putText(canvas, line, (60, y), cv2.FONT_HERSHEY_SIMPLEX, 1.15, (15, 15, 15), 2, cv2.LINE_AA)
        y += 82
    ok, buf = cv2.imencode(".png", canvas)
    assert ok
    return bytes(buf)


def _render_blurry_card() -> bytes:
    canvas = np.full((300, 420, 3), 210, dtype=np.uint8)
    cv2.putText(canvas, "blurry scan", (30, 140), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (195, 195, 195), 2)
    blurred = cv2.GaussianBlur(canvas, (31, 31), 15)
    ok, buf = cv2.imencode(".png", blurred)
    assert ok
    return bytes(buf)


def _create_full_draft_with_docs(
    client,
    mailbox,
    *,
    email: str = "asha.p4@example.com",
    full_name: str = "Asha Verma",
    dob: str = "1996-05-14",
    pan: str = "ABCPV1234F",
    education_level: str = "GRADUATE",
    board_name: str = "CBSE",
    result_status: str = "PASS",
    pan_card_name: str | None = None,
    aadhaar_name: str | None = None,
    aadhaar_dob: str = "14/05/1996",
    marksheet_name: str | None = None,
    holder_name: str | None = None,
    pan_blurry: bool = False,
    selfie_bad: bool = False,
) -> tuple[str, dict]:
    register(client, email=email, name=full_name)
    verify_user_email(client, mailbox, email)
    login(client, email)

    create_res = client.post("/api/v1/applications", json={"preferred_language": "EN"}, headers=csrf(client))
    assert create_res.status_code == 201, create_res.text
    app_id = create_res.json()["id"]

    patch_res = client.patch(
        f"/api/v1/applications/{app_id}",
        json={
            "current_step": 5,
            "preferred_language": "EN",
            "full_name": full_name,
            "date_of_birth": dob,
            "gender": "FEMALE",
            "father_or_spouse_name": "Ramesh Verma",
            "mobile": "9876543210",
            "email": email,
            "pan_number": pan,
            "aadhaar_last4": "9012",
            "address_line1": "42 MG Road",
            "city": "Bengaluru",
            "district": "Bengaluru Urban",
            "state": "Karnataka",
            "pincode": "560038",
            "same_as_permanent": True,
            "education_level": education_level,
            "board_name": board_name,
            "school_or_university": "National Public School",
            "passing_year": 2014,
            "roll_number": "CBSE-129044",
            "result_status": result_status,
            "percentage_or_cgpa": "86%",
            "account_holder_name": holder_name or full_name,
            "bank_name": "HDFC Bank",
            "branch_name": "Indiranagar",
            "ifsc_code": "HDFC0000240",
            "account_number": "50100123456789",
            "account_type": "SAVINGS",
            "is_joint_account": False,
            "is_primary_holder": True,
        },
        headers=csrf(client),
    )
    assert patch_res.status_code == 200, patch_res.text

    pan_bytes = (
        _render_blurry_card()
        if pan_blurry
        else _render_card(
            [
                "INCOME TAX DEPARTMENT",
                "GOVT OF INDIA",
                "Permanent Account Number",
                pan,
                (pan_card_name or full_name).upper(),
                "14/05/1996" if dob == "1996-05-14" else f"{dob[8:10]}/{dob[5:7]}/{dob[:4]}",
            ]
        )
    )
    aadhaar_bytes = _render_card(
        [
            "Unique Identification Authority of India",
            "Government of India",
            f"Name: {aadhaar_name or full_name}",
            f"DOB: {aadhaar_dob}",
            "4812 9304 9012",
        ]
    )
    aadhaar_back_bytes = _render_card(
        [
            "Unique Identification Authority of India",
            "Address: 42 MG Road Indiranagar Bengaluru Karnataka 560038",
            "4812 9304 9012",
        ]
    )
    marksheet_bytes = _render_card(
        [
            "CENTRAL BOARD OF SECONDARY EDUCATION",
            "CLASS X MARKSHEET CERTIFICATE",
            f"Candidate Name: {marksheet_name or full_name}",
            "Roll No: CBSE-129044",
            f"Result: {result_status}",
        ]
    )
    bank_bytes = _render_card(
        [
            "HDFC BANK LIMITED CANCELLED CHEQUE",
            f"Account Holder: {holder_name or full_name}",
            "IFSC: HDFC0000240",
            "A/C No: 50100123456789",
        ]
    )
    selfie_bytes = _render_blurry_card() if selfie_bad else (SPECIMEN_DIR / "Profile.jpg").read_bytes()

    uploads = [
        ("PAN_CARD", "pan.png", "image/png", pan_bytes),
        ("AADHAAR_FRONT", "aadhaar_f.png", "image/png", aadhaar_bytes),
        ("AADHAAR_BACK", "aadhaar_b.png", "image/png", aadhaar_back_bytes),
        ("CLASS_10_MARKSHEET", "marksheet.png", "image/png", marksheet_bytes),
        ("BANK_DOCUMENT", "cheque.png", "image/png", bank_bytes),
        ("APPLICANT_SELFIE", "selfie.jpg", "image/jpeg", selfie_bytes),
    ]
    for doc_type, fname, ctype, raw in uploads:
        up = client.post(
            f"/api/v1/applications/{app_id}/documents/{doc_type}",
            files={"file": (fname, raw, ctype)},
            headers=csrf(client),
        )
        assert up.status_code == 201, up.text

    sub = client.post(
        f"/api/v1/applications/{app_id}/submit",
        json={
            "consent_terms": True,
            "consent_kyc_processing": True,
            "declaration_no_other_posp": True,
        },
        headers=csrf(client),
    )
    assert sub.status_code == 200, sub.text
    return app_id, sub.json()


def test_ruleset_versioning_activation_and_safety_invariant(client):
    create_staff("ADMIN", "admin.rules@example.com")
    create_staff("REVIEWER", "rev.rules@example.com")

    login(client, "rev.rules@example.com")
    r_list = client.get("/api/v1/rulesets")
    assert r_list.status_code == 200
    assert any(rs["version"] == "3.2.0" and rs["is_active"] for rs in r_list.json())

    # Reviewer cannot create rulesets
    r_forbid = client.post(
        "/api/v1/rulesets",
        json={"version": "3.2.1", "name": "Unauthorized"},
        headers=csrf(client),
    )
    assert r_forbid.status_code == 403

    login(client, "admin.rules@example.com")
    # Safety invariant: never_auto_reject_name_mismatch cannot be disabled
    r_guardrail = client.post(
        "/api/v1/rulesets",
        json={
            "version": "3.9.0",
            "name": "Unsafe Rulebook",
            "rules_config": {"never_auto_reject_name_mismatch": False},
        },
        headers=csrf(client),
    )
    assert r_guardrail.status_code == 422

    # Admin creates draft 3.3.0 with manual sign-off required, then activates it
    r_create = client.post(
        "/api/v1/rulesets",
        json={
            "version": "3.3.0",
            "name": "Strict Human Sign-Off Policy",
            "description": "Require human reviewer sign-off for all clean applications",
            "rules_config": {"auto_approve_enabled": False},
            "activate_immediately": False,
        },
        headers=csrf(client),
    )
    assert r_create.status_code == 201
    rs_id = r_create.json()["id"]
    assert r_create.json()["is_active"] is False

    r_act = client.post(f"/api/v1/rulesets/{rs_id}/activate", headers=csrf(client))
    assert r_act.status_code == 200
    assert r_act.json()["is_active"] is True
    assert r_act.json()["status"] == "ACTIVE"

    versions = {rs["version"]: rs["is_active"] for rs in client.get("/api/v1/rulesets").json()}
    assert versions["3.3.0"] is True
    assert versions["3.2.0"] is False


def test_clean_application_auto_pass_and_posp_exclusivity(client, mailbox):
    app_id, submitted = _create_full_draft_with_docs(client, mailbox, email="clean.p4@example.com", pan="ABCPV5544K")
    assert submitted["status"] == "SUBMITTED"

    # Evaluate applies AUTO_PASS_ELIGIBLE -> KYC_APPROVED under default v3.2.0
    eval_res = client.post(
        f"/api/v1/applications/{app_id}/evaluate",
        json={"apply_transition": True},
        headers=csrf(client),
    )
    assert eval_res.status_code == 200, eval_res.text
    ev = eval_res.json()
    assert ev["outcome"] == "AUTO_PASS_ELIGIBLE"
    assert ev["recommended_status"] == "KYC_APPROVED"
    assert ev["auto_pass_eligible"] is True
    assert ev["rework_items"] == []

    detail = client.get(f"/api/v1/applications/{app_id}").json()
    assert detail["status"] == "KYC_APPROVED"

    # Second applicant attempting to register with same active KYC_APPROVED PAN triggers ALREADY_REGISTERED hard reject
    app2_id, _ = _create_full_draft_with_docs(client, mailbox, email="dup.pan@example.com", pan="ABCPV5544K")
    ev2 = client.post(
        f"/api/v1/applications/{app2_id}/evaluate",
        json={"apply_transition": True},
        headers=csrf(client),
    ).json()
    assert ev2["outcome"] == "REJECT_RECOMMENDED"
    assert ev2["recommended_status"] == "REJECTED"
    assert "ALREADY_REGISTERED" in ev2["reason_codes"]


def test_statutory_underage_pan_and_rejection_trumps_rework(client, mailbox):
    # Applicant is 16 years old AND uploaded blurry PAN -> Statutory rejection must trump rework!
    dob_minor = (date.today() - timedelta(days=16 * 365 + 10)).isoformat()
    app_id, _ = _create_full_draft_with_docs(
        client,
        mailbox,
        email="minor.blur@example.com",
        dob=dob_minor,
        pan="ABCTD1234F",  # 4th char T = Trust (not P Individual)
        pan_blurry=True,
    )
    with get_sessionmaker()() as db:
        app_row = db.get(Application, uuid.UUID(app_id))
        assert app_row is not None

    ev = client.post(f"/api/v1/applications/{app_id}/evaluate", headers=csrf(client)).json()
    assert ev["outcome"] == "REJECT_RECOMMENDED"
    assert ev["recommended_status"] == "REJECTED"
    assert "UNDERAGE" in ev["reason_codes"]
    assert "PAN_NOT_INDIVIDUAL" in ev["reason_codes"]
    assert ev["rework_items"] == []  # Rejection trumps rework


def test_name_mismatch_never_auto_rejects_and_requires_senior_decision(client, mailbox):
    create_staff("REVIEWER", "rev.nm@example.com")
    create_staff("SENIOR_REVIEWER", "sr.nm@example.com")
    create_staff("ADMIN", "admin.nm@example.com")

    app_id, _ = _create_full_draft_with_docs(
        client,
        mailbox,
        email="namemismatch@example.com",
        full_name="Asha Verma",
        pan_card_name="Asha Verma",
        aadhaar_name="Sandeep Kulkarni",  # Tier 7 NAME_MISMATCH!
    )
    ev = client.post(f"/api/v1/applications/{app_id}/evaluate", headers=csrf(client)).json()
    assert ev["outcome"] == "HUMAN_REVIEW"
    assert ev["recommended_status"] == "IN_REVIEW"
    assert "NAME_MISMATCH" in ev["reason_codes"]
    assert client.get(f"/api/v1/applications/{app_id}").json()["status"] == "IN_REVIEW"

    # Admin cannot decide (separation of duties)
    login(client, "admin.nm@example.com")
    r_adm = client.post(
        f"/api/v1/applications/{app_id}/decide",
        json={"decision": "APPROVE", "reason_codes": ["NAME_MISMATCH"], "reason_text": "Admin attempt override"},
        headers=csrf(client),
    )
    assert r_adm.status_code == 403

    # Standard reviewer cannot unilaterally approve/reject NAME_MISMATCH, must ESCALATE
    login(client, "rev.nm@example.com")
    r_rev = client.post(
        f"/api/v1/applications/{app_id}/decide",
        json={"decision": "APPROVE", "reason_codes": ["NAME_MISMATCH"], "reason_text": "Reviewer trying direct pass"},
        headers=csrf(client),
    )
    assert r_rev.status_code == 403
    assert r_rev.json()["error"]["code"] == "ESCALATED_DECISION_REQUIRED"

    r_esc = client.post(
        f"/api/v1/applications/{app_id}/decide",
        json={
            "decision": "ESCALATE",
            "reason_codes": ["NAME_MISMATCH"],
            "reason_text": "Escalating Tier 7 Aadhaar vs PAN name divergence to Senior Reviewer.",
        },
        headers=csrf(client),
    )
    assert r_esc.status_code == 200
    assert r_esc.json()["new_status"] == "IN_REVIEW"

    # Senior Reviewer confirms identity and approves override
    login(client, "sr.nm@example.com")
    r_sr = client.post(
        f"/api/v1/applications/{app_id}/decide",
        json={
            "decision": "APPROVE",
            "reason_codes": ["NAME_MISMATCH"],
            "reason_text": "Verified gazette name change certificate in supporting review; approved.",
        },
        headers=csrf(client),
    )
    assert r_sr.status_code == 200
    assert r_sr.json()["is_override"] is True
    assert r_sr.json()["new_status"] == "KYC_APPROVED"


def test_correction_vs_appeal_vs_reapplication_lifecycle(client, mailbox):
    create_staff("SENIOR_REVIEWER", "sr.appeal@example.com")

    # 1) CORRECTION PATH: blurry PAN -> NEEDS_MORE_INFO -> edit/reupload -> REWORK_SUBMITTED -> KYC_APPROVED
    app_id, _ = _create_full_draft_with_docs(
        client,
        mailbox,
        email="rework.user@example.com",
        pan="ABCPV2233G",
        pan_blurry=True,
    )
    ev = client.post(f"/api/v1/applications/{app_id}/evaluate", headers=csrf(client)).json()
    assert ev["outcome"] == "NEEDS_MORE_INFO"
    assert ev["recommended_status"] == "NEEDS_MORE_INFO"
    assert any(item["doc_type"] == "PAN_CARD" and item["title_hi"] for item in ev["rework_items"])

    # Applicant still cannot appeal or reapply while NEEDS_MORE_INFO
    assert (
        client.post(
            f"/api/v1/applications/{app_id}/appeal",
            json={"appeal_reason": "Trying to appeal before any rejection decision exists."},
            headers=csrf(client),
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/api/v1/applications/{app_id}/reapply",
            json={"reason": "Trying to reapply while rework is active."},
            headers=csrf(client),
        ).status_code
        == 409
    )

    # Re-upload crisp PAN and resubmit in-place (CORRECTION)
    crisp_pan = _render_card(
        ["INCOME TAX DEPARTMENT", "GOVT OF INDIA", "Permanent Account Number", "ABCPV2233G", "ASHA VERMA", "14/05/1996"]
    )
    up = client.post(
        f"/api/v1/applications/{app_id}/documents/PAN_CARD",
        files={"file": ("pan_fixed.png", crisp_pan, "image/png")},
        headers=csrf(client),
    )
    assert up.status_code == 201
    resub = client.post(
        f"/api/v1/applications/{app_id}/submit",
        json={"consent_terms": True, "consent_kyc_processing": True, "declaration_no_other_posp": True},
        headers=csrf(client),
    )
    assert resub.status_code == 200
    assert resub.json()["status"] == "REWORK_SUBMITTED"
    assert resub.json()["rework_count"] == 1
    assert resub.json()["resolution_kind"] == "CORRECTION"

    ev_fixed = client.post(f"/api/v1/applications/{app_id}/evaluate", headers=csrf(client)).json()
    assert ev_fixed["outcome"] == "AUTO_PASS_ELIGIBLE"
    assert client.get(f"/api/v1/applications/{app_id}").json()["status"] == "KYC_APPROVED"

    # 2) APPEAL vs REAPPLICATION PATH on a REJECTED application
    rej_id, _ = _create_full_draft_with_docs(
        client,
        mailbox,
        email="rej.user@example.com",
        pan="ABCTV4455H",  # Not individual ('T') -> REJECTED
    )
    ev_rej = client.post(f"/api/v1/applications/{rej_id}/evaluate", headers=csrf(client)).json()
    assert ev_rej["outcome"] == "REJECT_RECOMMENDED"
    assert client.get(f"/api/v1/applications/{rej_id}").json()["status"] == "REJECTED"

    # Submit formal Appeal
    ap_res = client.post(
        f"/api/v1/applications/{rej_id}/appeal",
        json={
            "appeal_reason": "Uploading my personal Individual PAN card because corporate PAN was selected earlier.",
            "supporting_notes": "Individual PAN prepared for verification.",
        },
        headers=csrf(client),
    )
    assert ap_res.status_code == 201
    appeal_id = ap_res.json()["id"]

    # Cannot start new Reapplication while OPEN appeal is pending
    r_block = client.post(
        f"/api/v1/applications/{rej_id}/reapply",
        json={"reason": "Want to bypass open appeal and start a new application immediately."},
        headers=csrf(client),
    )
    assert r_block.status_code == 409
    assert r_block.json()["error"]["code"] == "APPEAL_IN_PROGRESS"

    # Senior Reviewer upholds rejection on appeal -> Applicant can now formally Reapply
    login(client, "sr.appeal@example.com")
    res_uphold = client.post(
        f"/api/v1/applications/{rej_id}/appeals/{appeal_id}/resolve",
        json={
            "resolution": "UPHOLD_REJECTION",
            "resolution_notes": "Current submission contains Trust PAN; please start a fresh reapplication with your Individual ('P') PAN.",
        },
        headers=csrf(client),
    )
    assert res_uphold.status_code == 200
    assert res_uphold.json()["status"] == "REJECTED_UPHELD"

    # Applicant starts fresh linked Reapplication
    login(client, "rej.user@example.com")
    reapp_res = client.post(
        f"/api/v1/applications/{rej_id}/reapply",
        json={"reason": "Starting fresh application using my Individual PAN category P."},
        headers=csrf(client),
    )
    assert reapp_res.status_code == 201, reapp_res.text
    child = reapp_res.json()
    assert child["parent_application_id"] == rej_id
    assert child["resolution_kind"] == "REAPPLICATION"
    assert child["status"] == "DRAFT"

    # Audit & Decision history populated and free of leaked raw PII
    summary = client.get(f"/api/v1/applications/{rej_id}/decisions").json()
    assert len(summary["execution_history"]) >= 1
    assert len(summary["appeals"]) == 1
    with get_sessionmaker()() as db:
        exec_rows = list(
            db.scalars(select(RuleExecution).where(RuleExecution.application_id == uuid.UUID(rej_id))).all()
        )
        assert len(exec_rows) >= 1
        events = list(
            db.scalars(select(ApplicationEvent).where(ApplicationEvent.application_id == uuid.UUID(rej_id))).all()
        )
        assert any(e.event_type == "APPEAL_SUBMITTED" for e in events)
        logs = list(db.scalars(select(AuditLog)).all())
        assert all("ABCTV4455H" not in str(log.details) for log in logs)
