"""Phase 5 reviewer operations: queue filtering, claim/assign, fraud desk, review history, and analytics."""

from __future__ import annotations

import uuid
from collections import defaultdict

from fastapi import Request
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import AuthContext
from app.core.errors import AppError
from app.models import (
    Application,
    ApplicationAppeal,
    ApplicationDecision,
    ApplicationEvent,
    DocumentFieldCorrection,
    Role,
    RuleExecution,
    User,
)
from app.models.application import REQUIRED_DOC_TYPES
from app.models.base import utcnow
from app.schemas.review import (
    AssignableReviewerOut,
    FraudEscalationRequest,
    FraudResolutionRequest,
    ReviewAnalyticsOut,
    ReviewClaimRequest,
    ReviewerProductivityOut,
    ReviewHistoryItemOut,
    ReviewHistoryPageOut,
    ReviewQueueItemOut,
    ReviewQueueKpis,
    ReviewQueuePageOut,
)
from app.services import audit
from app.services.applications import get_application
from app.services.notifications import create_notification

PENDING_REVIEW_STATUSES = ("SUBMITTED", "REWORK_SUBMITTED", "IN_REVIEW")


def _abac_app_stmt(auth: AuthContext):
    stmt = select(Application).where(Application.sensitivity <= auth.user.clearance_level)
    if auth.user.region not in (None, "ALL"):
        stmt = stmt.where(Application.region == auth.user.region)
    return stmt


def _latest_executions_map(db: Session, app_ids: list[uuid.UUID]) -> dict[uuid.UUID, RuleExecution]:
    if not app_ids:
        return {}
    rows = db.scalars(
        select(RuleExecution)
        .where(RuleExecution.application_id.in_(app_ids))
        .order_by(RuleExecution.application_id, desc(RuleExecution.executed_at))
    ).all()
    out: dict[uuid.UUID, RuleExecution] = {}
    for row in rows:
        if row.application_id not in out:
            out[row.application_id] = row
    return out


def _open_appeals_count_map(db: Session, app_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not app_ids:
        return {}
    rows = db.execute(
        select(ApplicationAppeal.application_id, func.count(ApplicationAppeal.id))
        .where(ApplicationAppeal.application_id.in_(app_ids), ApplicationAppeal.status == "OPEN")
        .group_by(ApplicationAppeal.application_id)
    ).all()
    return {row[0]: int(row[1]) for row in rows}


def get_review_queue(
    db: Session,
    auth: AuthContext,
    *,
    q: str | None = None,
    status: str | None = None,
    region: str | None = None,
    queue_view: str = "pending",
    outcome: str | None = None,
    sort_by: str = "urgency",
    page: int = 1,
    page_size: int = 20,
) -> ReviewQueuePageOut:
    # Load ABAC-scoped applications for live KPIs and flexible filtering
    all_apps = list(db.scalars(_abac_app_stmt(auth).options(selectinload(Application.documents))).all())
    all_ids = [a.id for a in all_apps]
    latest_execs = _latest_executions_map(db, all_ids)
    open_appeals = _open_appeals_count_map(db, all_ids)

    reviewer_ids = {a.assigned_reviewer_id for a in all_apps if a.assigned_reviewer_id is not None}
    reviewer_names: dict[uuid.UUID, str] = {}
    if reviewer_ids:
        for uid, fname in db.execute(select(User.id, User.full_name).where(User.id.in_(reviewer_ids))).all():
            reviewer_names[uid] = fname

    kpis = ReviewQueueKpis(
        pending_review_count=sum(1 for a in all_apps if a.status in PENDING_REVIEW_STATUSES),
        submitted_count=sum(1 for a in all_apps if a.status == "SUBMITTED"),
        rework_submitted_count=sum(1 for a in all_apps if a.status == "REWORK_SUBMITTED"),
        in_review_count=sum(1 for a in all_apps if a.status == "IN_REVIEW"),
        escalated_count=sum(1 for a in all_apps if a.escalated_at is not None and a.status in PENDING_REVIEW_STATUSES),
        fraud_flagged_count=sum(1 for a in all_apps if a.fraud_flag),
        open_appeals_count=sum(open_appeals.values()),
        assigned_to_me_count=sum(1 for a in all_apps if a.assigned_reviewer_id == auth.user.id),
        unassigned_pending_count=sum(
            1 for a in all_apps if a.status in PENDING_REVIEW_STATUSES and a.assigned_reviewer_id is None
        ),
        kyc_approved_count=sum(1 for a in all_apps if a.status == "KYC_APPROVED"),
        rejected_count=sum(1 for a in all_apps if a.status == "REJECTED"),
    )

    q_clean = (q or "").strip().lower()
    region_clean = (region or "").strip().upper()
    status_tokens = {s.strip().upper() for s in (status or "").split(",") if s.strip()}

    filtered: list[Application] = []
    for app in all_apps:
        ex = latest_execs.get(app.id)
        appeal_cnt = open_appeals.get(app.id, 0)

        if queue_view == "pending" and app.status not in (*PENDING_REVIEW_STATUSES, "NEEDS_MORE_INFO"):
            continue
        if queue_view == "assigned_to_me" and app.assigned_reviewer_id != auth.user.id:
            continue
        if queue_view == "unassigned" and (
            app.assigned_reviewer_id is not None or app.status not in PENDING_REVIEW_STATUSES
        ):
            continue
        if queue_view == "escalated" and app.escalated_at is None:
            continue
        if queue_view == "fraud" and not app.fraud_flag:
            continue
        if queue_view == "open_appeals" and appeal_cnt == 0:
            continue

        if status_tokens and "ALL" not in status_tokens and app.status not in status_tokens:
            continue
        if region_clean and region_clean != "ALL" and (app.region or "").upper() != region_clean:
            continue
        if outcome and outcome.upper() != "ALL" and (ex.outcome if ex else None) != outcome.upper():
            continue

        if q_clean:
            haystack = " ".join(
                filter(
                    None,
                    [
                        app.reference_code,
                        app.full_name,
                        app.city,
                        app.state,
                        app.region,
                        app.aadhaar_last4,
                    ],
                )
            ).lower()
            if q_clean not in haystack:
                continue

        filtered.append(app)

    def _urgency_key(a: Application):
        ex = latest_execs.get(a.id)
        is_appeal = 1 if open_appeals.get(a.id, 0) > 0 else 0
        status_rank = {
            "IN_REVIEW": 0,
            "REWORK_SUBMITTED": 1,
            "SUBMITTED": 2,
            "NEEDS_MORE_INFO": 3,
            "DRAFT": 4,
            "KYC_APPROVED": 5,
            "REJECTED": 6,
            "WITHDRAWN": 7,
        }.get(a.status, 8)
        ts = (a.submitted_at or a.last_saved_at).timestamp()
        return (
            0 if a.fraud_flag else 1,
            0 if is_appeal else 1,
            0 if (a.escalated_at is not None or (ex and ex.requires_human_review)) else 1,
            status_rank,
            ts,
        )

    if sort_by == "oldest_submitted":
        filtered.sort(key=lambda a: (a.submitted_at or a.last_saved_at))
    elif sort_by == "newest_submitted":
        filtered.sort(key=lambda a: (a.submitted_at or a.last_saved_at), reverse=True)
    else:
        filtered.sort(key=_urgency_key)

    total = len(filtered)
    start = (page - 1) * page_size
    page_apps = filtered[start : start + page_size]

    items: list[ReviewQueueItemOut] = []
    for app in page_apps:
        ex = latest_execs.get(app.id)
        current_docs = [d for d in app.documents if d.is_current]
        items.append(
            ReviewQueueItemOut(
                id=app.id,
                reference_code=app.reference_code,
                status=app.status,
                region=app.region,
                sensitivity=app.sensitivity,
                full_name=app.full_name,
                city=app.city,
                state=app.state,
                submitted_at=app.submitted_at,
                last_saved_at=app.last_saved_at,
                rework_count=app.rework_count,
                resolution_kind=app.resolution_kind,
                assigned_reviewer_id=app.assigned_reviewer_id,
                assigned_reviewer_name=reviewer_names.get(app.assigned_reviewer_id)
                if app.assigned_reviewer_id
                else None,
                assigned_at=app.assigned_at,
                escalated_at=app.escalated_at,
                escalation_reason=app.escalation_reason,
                fraud_flag=app.fraud_flag,
                fraud_reason=app.fraud_reason,
                fraud_escalated_at=app.fraud_escalated_at,
                latest_outcome=ex.outcome if ex else None,
                latest_reason_codes=list(ex.reason_codes or []) if ex else [],
                open_appeal_count=open_appeals.get(app.id, 0),
                uploaded_document_count=len(current_docs),
                required_document_count=len(REQUIRED_DOC_TYPES),
            )
        )

    return ReviewQueuePageOut(items=items, total=total, page=page, page_size=page_size, kpis=kpis)


def list_assignable_reviewers(db: Session, auth: AuthContext) -> list[AssignableReviewerOut]:
    stmt = (
        select(User, Role.code)
        .join(Role, User.role_id == Role.id)
        .where(User.is_active.is_(True), Role.code.in_(("REVIEWER", "SENIOR_REVIEWER")))
        .order_by(User.full_name.asc())
    )
    if auth.user.region not in (None, "ALL"):
        stmt = stmt.where(or_(User.region == auth.user.region, User.region == "ALL", User.region.is_(None)))
    rows = db.execute(stmt).all()
    return [
        AssignableReviewerOut(
            id=u.id,
            full_name=u.full_name,
            email=u.email,
            role_code=role_code,
            region=u.region,
        )
        for u, role_code in rows
    ]


def claim_or_assign_application(
    db: Session,
    app: Application,
    body: ReviewClaimRequest,
    auth: AuthContext,
    request: Request,
) -> Application:
    if app.status in ("DRAFT", "WITHDRAWN"):
        raise AppError(409, "INVALID_STATUS_FOR_ASSIGNMENT", "Draft or withdrawn applications cannot be claimed.")

    now = utcnow()
    prev_status = app.status

    if body.action == "release":
        app.assigned_reviewer_id = None
        app.assigned_at = None
        event_type = "REVIEW_RELEASED"
        summary = f"Assignment released by {auth.user.full_name}."
        audit_action = "review.released"
        details = {"reference_code": app.reference_code}
    elif body.action == "assign":
        if "application:decide_escalated" not in auth.permissions:
            raise AppError(403, "FORBIDDEN", "Only Senior Reviewers can reassign applications to other reviewers.")
        if body.target_user_id is None:
            raise AppError(422, "TARGET_USER_REQUIRED", "Specify target_user_id when assigning an application.")
        target = db.get(User, body.target_user_id)
        if target is None or not target.is_active or target.role.code not in ("REVIEWER", "SENIOR_REVIEWER"):
            raise AppError(404, "REVIEWER_NOT_FOUND", "Target user is not an active reviewer.")
        app.assigned_reviewer_id = target.id
        app.assigned_at = now
        if app.status in ("SUBMITTED", "REWORK_SUBMITTED"):
            app.status = "IN_REVIEW"
        event_type = "REVIEW_ASSIGNED"
        summary = f"Assigned to {target.full_name} ({target.role.code}) by {auth.user.full_name}."
        audit_action = "review.assigned"
        details = {"reference_code": app.reference_code, "assigned_to_user_id": str(target.id)}
    else:
        app.assigned_reviewer_id = auth.user.id
        app.assigned_at = now
        if app.status in ("SUBMITTED", "REWORK_SUBMITTED"):
            app.status = "IN_REVIEW"
        event_type = "REVIEW_CLAIMED"
        summary = f"Claimed for review by {auth.user.full_name} ({auth.user.role.code})."
        audit_action = "review.claimed"
        details = {"reference_code": app.reference_code}

    app.last_saved_at = now
    db.add(
        ApplicationEvent(
            application_id=app.id,
            actor_user_id=auth.user.id,
            actor_role=auth.user.role.code,
            event_type=event_type,
            from_status=prev_status,
            to_status=app.status,
            summary=summary,
            details=details,
        )
    )
    audit.add(
        db,
        request,
        audit_action,
        actor=auth.user,
        resource_type="application",
        resource_id=str(app.id),
        details=details,
    )
    db.flush()
    return get_application(db, app.id)


def escalate_to_fraud_desk(
    db: Session,
    app: Application,
    body: FraudEscalationRequest,
    auth: AuthContext,
    request: Request,
) -> Application:
    if app.status in ("DRAFT", "WITHDRAWN"):
        raise AppError(409, "INVALID_STATUS_FOR_FRAUD_ESCALATION", "Cannot escalate a draft or withdrawn application.")

    now = utcnow()
    prev_status = app.status
    clean_reason = body.reason.strip()

    app.fraud_flag = True
    app.fraud_reason = clean_reason
    app.fraud_escalated_at = now
    app.escalated_at = app.escalated_at or now
    app.escalated_by_user_id = auth.user.id
    app.escalation_reason = clean_reason
    app.status = "IN_REVIEW"
    app.last_saved_at = now

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
            decision="ESCALATE",
            previous_status=prev_status,
            new_status="IN_REVIEW",
            is_override=False,
            override_of_outcome=None,
            reason_codes=["REVIEWER_DISCRETION"],
            reason_text=f"[FRAUD DESK ESCALATION] {clean_reason}",
            rework_items=[],
        )
    )
    db.add(
        ApplicationEvent(
            application_id=app.id,
            actor_user_id=auth.user.id,
            actor_role=auth.user.role.code,
            event_type="FRAUD_ESCALATED",
            from_status=prev_status,
            to_status="IN_REVIEW",
            summary=f"Escalated to Fraud Desk by {auth.user.full_name} ({auth.user.role.code}).",
            details={"fraud_reason": clean_reason},
        )
    )
    create_notification(
        db,
        user_id=app.user_id,
        application_id=app.id,
        category="REVIEWER_DECISION",
        title=f"Application {app.reference_code} under enhanced review",
        body="Your application has been escalated for specialist verification review.",
        action_url=f"/app/applications/{app.id}",
    )
    audit.add(
        db,
        request,
        "application.fraud_escalated",
        actor=auth.user,
        resource_type="application",
        resource_id=str(app.id),
        details={"reference_code": app.reference_code, "from_status": prev_status},
    )
    db.flush()
    return get_application(db, app.id)


def resolve_fraud_escalation(
    db: Session,
    app: Application,
    body: FraudResolutionRequest,
    auth: AuthContext,
    request: Request,
) -> Application:
    if not app.fraud_flag:
        raise AppError(409, "NOT_FRAUD_FLAGGED", "This application is not currently flagged for fraud review.")

    now = utcnow()
    prev_status = app.status
    clean_reason = body.reason_text.strip()
    latest_exec = db.scalar(
        select(RuleExecution)
        .where(RuleExecution.application_id == app.id)
        .order_by(desc(RuleExecution.executed_at))
        .limit(1)
    )

    app.fraud_flag = False
    app.last_saved_at = now

    if body.resolution == "CONFIRM_FRAUD_REJECT":
        app.status = "REJECTED"
        decision_label = "REJECT"
        event_type = "FRAUD_CONFIRMED_REJECTED"
        summary = f"Fraud Desk confirmed anomaly and rejected application ({auth.user.full_name})."
        audit_action = "application.fraud_confirmed_rejected"
    else:
        decision_label = "ESCALATE"
        event_type = "FRAUD_CLEARED"
        summary = f"Fraud flag cleared by {auth.user.full_name}; returned to normal review."
        audit_action = "application.fraud_cleared"

    db.add(
        ApplicationDecision(
            application_id=app.id,
            rule_execution_id=latest_exec.id if latest_exec else None,
            decided_by_user_id=auth.user.id,
            decided_by_role=auth.user.role.code,
            decision=decision_label,
            previous_status=prev_status,
            new_status=app.status,
            is_override=False,
            override_of_outcome=None,
            reason_codes=["REVIEWER_DISCRETION"],
            reason_text=f"[{body.resolution}] {clean_reason}",
            rework_items=[],
        )
    )
    db.add(
        ApplicationEvent(
            application_id=app.id,
            actor_user_id=auth.user.id,
            actor_role=auth.user.role.code,
            event_type=event_type,
            from_status=prev_status,
            to_status=app.status,
            summary=summary,
            details={"resolution": body.resolution},
        )
    )
    create_notification(
        db,
        user_id=app.user_id,
        application_id=app.id,
        category="REVIEWER_DECISION",
        title=f"Review update for {app.reference_code}",
        body=clean_reason,
        action_url=f"/app/applications/{app.id}",
    )
    audit.add(
        db,
        request,
        audit_action,
        actor=auth.user,
        resource_type="application",
        resource_id=str(app.id),
        details={"reference_code": app.reference_code, "resolution": body.resolution, "to_status": app.status},
    )
    db.flush()
    return get_application(db, app.id)


def get_review_history(
    db: Session,
    auth: AuthContext,
    *,
    mine_only: bool = False,
    decision: str | None = None,
    page: int = 1,
    page_size: int = 25,
) -> ReviewHistoryPageOut:
    stmt = (
        select(ApplicationDecision, Application, User.full_name)
        .join(Application, ApplicationDecision.application_id == Application.id)
        .join(User, ApplicationDecision.decided_by_user_id == User.id)
        .where(Application.sensitivity <= auth.user.clearance_level)
    )
    if auth.user.region not in (None, "ALL"):
        stmt = stmt.where(Application.region == auth.user.region)
    if mine_only:
        stmt = stmt.where(ApplicationDecision.decided_by_user_id == auth.user.id)
    if decision and decision.upper() != "ALL":
        stmt = stmt.where(ApplicationDecision.decision == decision.upper())

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.execute(
        stmt.order_by(desc(ApplicationDecision.created_at)).offset((page - 1) * page_size).limit(page_size)
    ).all()

    items = [
        ReviewHistoryItemOut(
            decision_id=dec.id,
            application_id=app.id,
            reference_code=app.reference_code,
            applicant_name=app.full_name,
            region=app.region,
            decided_by_user_id=dec.decided_by_user_id,
            decided_by_name=actor_name,
            decided_by_role=dec.decided_by_role,
            decision=dec.decision,
            previous_status=dec.previous_status,
            new_status=dec.new_status,
            is_override=dec.is_override,
            override_of_outcome=dec.override_of_outcome,
            reason_codes=list(dec.reason_codes or []),
            reason_text=dec.reason_text,
            created_at=dec.created_at,
        )
        for dec, app, actor_name in rows
    ]
    return ReviewHistoryPageOut(items=items, total=int(total), page=page, page_size=page_size)


def get_review_analytics(db: Session, auth: AuthContext) -> ReviewAnalyticsOut:
    apps = list(db.scalars(_abac_app_stmt(auth)).all())
    active_pool = [a for a in apps if a.status not in ("DRAFT", "WITHDRAWN")]
    pool_ids = [a.id for a in active_pool]

    status_counts: dict[str, int] = defaultdict(int)
    for a in apps:
        status_counts[a.status] += 1

    latest_execs = _latest_executions_map(db, pool_ids)
    rule_outcome_counts: dict[str, int] = defaultdict(int)
    for ex in latest_execs.values():
        rule_outcome_counts[ex.outcome] += 1

    total_n = len(active_pool)
    stp_count = sum(1 for ex in latest_execs.values() if ex.auto_pass_eligible)
    rework_any_count = sum(1 for a in active_pool if a.rework_count > 0 or a.status == "NEEDS_MORE_INFO")
    escalated_any_count = sum(1 for a in active_pool if a.escalated_at is not None or a.fraud_flag)

    stp_rate = round((stp_count / total_n) * 100, 1) if total_n else 0.0
    rework_rate = round((rework_any_count / total_n) * 100, 1) if total_n else 0.0
    esc_rate = round((escalated_any_count / total_n) * 100, 1) if total_n else 0.0

    # Turnaround from submitted_at to earliest human decision per application
    turnarounds: list[float] = []
    decisions_rows: list[tuple[ApplicationDecision, User, str]] = []
    corrections_by_user: dict[uuid.UUID, int] = defaultdict(int)
    open_appeals = 0
    resolved_appeals = 0

    if pool_ids:
        dec_query = db.execute(
            select(ApplicationDecision, User, Role.code)
            .join(User, ApplicationDecision.decided_by_user_id == User.id)
            .join(Role, User.role_id == Role.id)
            .where(ApplicationDecision.application_id.in_(pool_ids))
            .order_by(ApplicationDecision.created_at.asc())
        ).all()
        decisions_rows = list(dec_query)

        first_decision_at: dict[uuid.UUID, object] = {}
        for dec, _, _ in decisions_rows:
            if dec.application_id not in first_decision_at:
                first_decision_at[dec.application_id] = dec.created_at
        for a in active_pool:
            if a.submitted_at and a.id in first_decision_at:
                delta_h = (first_decision_at[a.id] - a.submitted_at).total_seconds() / 3600.0
                if delta_h >= 0:
                    turnarounds.append(delta_h)

        for uid, cnt in db.execute(
            select(DocumentFieldCorrection.corrected_by_user_id, func.count(DocumentFieldCorrection.id))
            .where(
                DocumentFieldCorrection.application_id.in_(pool_ids),
                DocumentFieldCorrection.corrected_by_user_id.is_not(None),
            )
            .group_by(DocumentFieldCorrection.corrected_by_user_id)
        ).all():
            if uid is not None:
                corrections_by_user[uid] = int(cnt)

        for status_val, cnt in db.execute(
            select(ApplicationAppeal.status, func.count(ApplicationAppeal.id))
            .where(ApplicationAppeal.application_id.in_(pool_ids))
            .group_by(ApplicationAppeal.status)
        ).all():
            if status_val == "OPEN":
                open_appeals += int(cnt)
            else:
                resolved_appeals += int(cnt)

    avg_turnaround = round(sum(turnarounds) / len(turnarounds), 2) if turnarounds else None

    prod_map: dict[uuid.UUID, dict] = {}
    for dec, u, rcode in decisions_rows:
        bucket = prod_map.setdefault(
            u.id,
            {
                "user_id": u.id,
                "full_name": u.full_name,
                "role_code": rcode,
                "decisions_count": 0,
                "approvals_count": 0,
                "rework_count": 0,
                "rejections_count": 0,
                "escalations_count": 0,
                "overrides_count": 0,
                "field_corrections_count": corrections_by_user.get(u.id, 0),
            },
        )
        bucket["decisions_count"] += 1
        if dec.decision == "APPROVE":
            bucket["approvals_count"] += 1
        elif dec.decision == "NEEDS_MORE_INFO":
            bucket["rework_count"] += 1
        elif dec.decision == "REJECT":
            bucket["rejections_count"] += 1
        elif dec.decision == "ESCALATE":
            bucket["escalations_count"] += 1
        if dec.is_override:
            bucket["overrides_count"] += 1

    productivity = [
        ReviewerProductivityOut(**v)
        for v in sorted(prod_map.values(), key=lambda x: (-x["decisions_count"], x["full_name"]))
    ]

    return ReviewAnalyticsOut(
        total_submitted_or_decided=total_n,
        status_counts=dict(status_counts),
        rule_outcome_counts=dict(rule_outcome_counts),
        stp_auto_pass_rate_pct=stp_rate,
        rework_rate_pct=rework_rate,
        escalation_rate_pct=esc_rate,
        fraud_flagged_active_count=sum(1 for a in apps if a.fraud_flag),
        avg_turnaround_hours=avg_turnaround,
        open_appeals_count=open_appeals,
        resolved_appeals_count=resolved_appeals,
        reviewer_productivity=productivity,
    )
