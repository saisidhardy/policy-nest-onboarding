from __future__ import annotations

import uuid

from sqlalchemy import select

from app.core.db import get_sessionmaker
from app.models import AuditLog
from tests.conftest import create_staff, csrf, login
from tests.test_phase4_rules import _create_full_draft_with_docs


def _submit_south_and_north_apps(client, mailbox):
    # Clean SOUTH app -> IN_REVIEW via NAME_MISMATCH (ready for queue/claim/fraud/escalate)
    south_id, _ = _create_full_draft_with_docs(
        client,
        mailbox,
        email="south.app@example.com",
        full_name="Asha Verma",
        pan="ABCPV7711K",
        pan_card_name="Asha Verma",
        aadhaar_name="Rohan Deshmukh",  # Tier 7 NAME_MISMATCH
    )
    client.post(f"/api/v1/applications/{south_id}/evaluate", headers=csrf(client)).raise_for_status()

    # Second SOUTH app -> NEEDS_MORE_INFO (blurry PAN)
    south_rework_id, _ = _create_full_draft_with_docs(
        client,
        mailbox,
        email="south.rework@example.com",
        full_name="Meera Nair",
        pan="ABCPN7722M",
        pan_blurry=True,
    )
    client.post(f"/api/v1/applications/{south_rework_id}/evaluate", headers=csrf(client)).raise_for_status()
    return south_id, south_rework_id


def test_review_queue_kpis_filters_search_and_claim_assignment(client, mailbox):
    create_staff("REVIEWER", "rev.south@example.com", name="South Officer", region="SOUTH", clearance=2)
    create_staff("REVIEWER", "rev.north@example.com", name="North Officer", region="NORTH", clearance=2)
    create_staff("SENIOR_REVIEWER", "sr.south@example.com", name="South Senior", region="SOUTH", clearance=3)

    south_id, south_rework_id = _submit_south_and_north_apps(client, mailbox)

    # NORTH reviewer must NOT see SOUTH applications in queue or history
    login(client, "rev.north@example.com")
    q_north = client.get("/api/v1/review/queue?queue_view=all").json()
    assert q_north["total"] == 0
    assert q_north["kpis"]["pending_review_count"] == 0

    # SOUTH reviewer sees both SOUTH applications + live KPIs
    login(client, "rev.south@example.com")
    q_all = client.get("/api/v1/review/queue?queue_view=all").json()
    assert q_all["total"] == 2
    assert q_all["kpis"]["pending_review_count"] == 1  # south_id is IN_REVIEW
    assert q_all["kpis"]["unassigned_pending_count"] == 1

    # Search by applicant name narrows queue cleanly
    q_search = client.get("/api/v1/review/queue?queue_view=all&q=Meera").json()
    assert q_search["total"] == 1
    assert q_search["items"][0]["id"] == south_rework_id

    # Filter by rule outcome
    q_outcome = client.get("/api/v1/review/queue?queue_view=all&outcome=HUMAN_REVIEW").json()
    assert q_outcome["total"] == 1
    assert q_outcome["items"][0]["id"] == south_id

    # Claim application
    r_claim = client.post(
        f"/api/v1/review/applications/{south_id}/claim",
        json={"action": "claim"},
        headers=csrf(client),
    )
    assert r_claim.status_code == 200
    assert r_claim.json()["assigned_reviewer_id"] is not None

    q_mine = client.get("/api/v1/review/queue?queue_view=assigned_to_me").json()
    assert q_mine["total"] == 1
    assert q_mine["items"][0]["assigned_reviewer_name"] == "South Officer"

    # Standard reviewer cannot assign to another reviewer
    rev_list = client.get("/api/v1/review/reviewers").json()
    sr_user = next(u for u in rev_list if u["role_code"] == "SENIOR_REVIEWER")
    r_forbid_assign = client.post(
        f"/api/v1/review/applications/{south_id}/claim",
        json={"action": "assign", "target_user_id": sr_user["id"]},
        headers=csrf(client),
    )
    assert r_forbid_assign.status_code == 403

    # Release and let Senior Reviewer assign to South Senior
    client.post(
        f"/api/v1/review/applications/{south_id}/claim", json={"action": "release"}, headers=csrf(client)
    ).raise_for_status()
    login(client, "sr.south@example.com")
    r_assign = client.post(
        f"/api/v1/review/applications/{south_id}/claim",
        json={"action": "assign", "target_user_id": sr_user["id"]},
        headers=csrf(client),
    )
    assert r_assign.status_code == 200
    assert r_assign.json()["assigned_reviewer_id"] == sr_user["id"]


def test_fraud_escalation_resolution_history_and_analytics_rbac(client, mailbox):
    create_staff("REVIEWER", "rev.ops@example.com", name="Ops Reviewer", region="SOUTH", clearance=2)
    create_staff("SENIOR_REVIEWER", "sr.ops@example.com", name="Lead Senior", region="SOUTH", clearance=3)
    create_staff("ADMIN", "admin.ops@example.com", name="Ops Admin", region="ALL", clearance=3)

    south_id, south_rework_id = _submit_south_and_north_apps(client, mailbox)

    # Ops Reviewer escalates south_id to Fraud Desk
    login(client, "rev.ops@example.com")
    r_fraud = client.post(
        f"/api/v1/review/applications/{south_id}/fraud-escalate",
        json={"reason": "Suspected altered Aadhaar photo alignment during manual verification inspection."},
        headers=csrf(client),
    )
    assert r_fraud.status_code == 200
    assert r_fraud.json()["fraud_flag"] is True
    assert r_fraud.json()["status"] == "IN_REVIEW"

    # Fraud queue filter surfaces flagged application
    q_fraud = client.get("/api/v1/review/queue?queue_view=fraud").json()
    assert q_fraud["total"] == 1
    assert q_fraud["items"][0]["id"] == south_id
    assert q_fraud["kpis"]["fraud_flagged_count"] == 1

    # Standard reviewer cannot resolve fraud escalation OR access org-wide analytics
    r_forbid_res = client.post(
        f"/api/v1/review/applications/{south_id}/fraud-resolve",
        json={"resolution": "CLEAR_FLAG", "reason_text": "Attempted unauthorized fraud clearance."},
        headers=csrf(client),
    )
    assert r_forbid_res.status_code == 403
    assert client.get("/api/v1/review/analytics").status_code == 403

    # Lead Senior clears fraud flag and approves KYC, then checks review history + analytics
    login(client, "sr.ops@example.com")
    r_clear = client.post(
        f"/api/v1/review/applications/{south_id}/fraud-resolve",
        json={
            "resolution": "CLEAR_FLAG",
            "reason_text": "Original Aadhaar card confirmed authentic via supporting verification.",
        },
        headers=csrf(client),
    )
    assert r_clear.status_code == 200
    assert r_clear.json()["fraud_flag"] is False

    r_approve = client.post(
        f"/api/v1/applications/{south_id}/decide",
        json={
            "decision": "APPROVE",
            "reason_codes": ["NAME_MISMATCH"],
            "reason_text": "Verified supporting gazette record; Senior Reviewer approves KYC.",
        },
        headers=csrf(client),
    )
    assert r_approve.status_code == 200

    # Review history lists decisions with authenticated actor details and reason text
    hist_all = client.get("/api/v1/review/history").json()
    assert hist_all["total"] == 3  # ESCALATE + CLEAR_FLAG + APPROVE
    assert any(h["decided_by_name"] == "Ops Reviewer" and h["decision"] == "ESCALATE" for h in hist_all["items"])
    assert any(
        h["decided_by_name"] == "Lead Senior" and h["decision"] == "APPROVE" and h["is_override"]
        for h in hist_all["items"]
    )

    hist_mine = client.get("/api/v1/review/history?mine_only=true&decision=APPROVE").json()
    assert hist_mine["total"] == 1
    assert hist_mine["items"][0]["reference_code"].startswith("APP-")

    # Analytics endpoint works for SENIOR_REVIEWER and ADMIN
    an_sr = client.get("/api/v1/review/analytics").json()
    assert an_sr["total_submitted_or_decided"] == 2
    assert an_sr["rework_rate_pct"] == 50.0
    assert an_sr["escalation_rate_pct"] == 50.0
    assert an_sr["avg_turnaround_hours"] is not None
    assert len(an_sr["reviewer_productivity"]) == 2
    sr_stats = next(p for p in an_sr["reviewer_productivity"] if p["role_code"] == "SENIOR_REVIEWER")
    assert sr_stats["approvals_count"] == 1 and sr_stats["overrides_count"] == 1

    login(client, "admin.ops@example.com")
    assert client.get("/api/v1/review/analytics").status_code == 200

    # Verify audit entries recorded for claim/fraud/decide
    with get_sessionmaker()() as db:
        actions = {
            row.action
            for row in db.scalars(select(AuditLog).where(AuditLog.resource_id == str(uuid.UUID(south_id)))).all()
        }
        assert "application.fraud_escalated" in actions
        assert "application.fraud_cleared" in actions
        assert "application.decided" in actions
