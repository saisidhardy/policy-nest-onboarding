"""Phase 6 Training & Certification domain service with LMS sync & retry handling."""

import uuid
from datetime import timedelta
from decimal import Decimal
from math import ceil

from fastapi import Request
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import AuthContext
from app.core.errors import AppError
from app.models import Application, ApplicationEvent, LmsSyncLog, TrainingRecord, User
from app.models.base import utcnow
from app.rbac.catalog import RoleCode
from app.schemas.training import (
    BatchRetryOut,
    CurriculumModuleProgressOut,
    LmsAdapterStatusOut,
    LmsSyncLogOut,
    LmsWebhookPayload,
    TrainingOverviewOut,
    TrainingQueueItemOut,
    TrainingRecordOut,
)
from app.services import audit, lms_adapter
from app.services.applications import create_notification
from app.services.platform_config import get_effective_lms_config

ELIGIBLE_APP_STATUSES = {"KYC_APPROVED", "TRAINING_IN_PROGRESS", "CERTIFIED"}


def evaluate_eligibility(app: Application) -> tuple[str, str]:
    if app.status in ELIGIBLE_APP_STATUSES:
        return (
            "ELIGIBLE",
            "Application has passed PolicyNest KYC checks and is eligible for 15-hour IRDAI POSP training.",
        )
    if app.status == "REJECTED":
        return ("NOT_ELIGIBLE", "Rejected applications are ineligible for POSP training.")
    if app.status == "WITHDRAWN":
        return ("NOT_ELIGIBLE", "Withdrawn applications are ineligible for POSP training.")
    return (
        "NOT_ELIGIBLE",
        f"KYC approval is required before POSP training enrollment (current status: {app.status}).",
    )


def get_or_create_training_record(db: Session, app: Application) -> TrainingRecord:
    record = db.scalar(
        select(TrainingRecord)
        .options(selectinload(TrainingRecord.sync_logs))
        .where(TrainingRecord.application_id == app.id)
    )
    elig_status, elig_reason = evaluate_eligibility(app)
    s = get_effective_lms_config(db)

    if record is None:
        record = TrainingRecord(
            application_id=app.id,
            eligibility_status=elig_status,
            eligibility_reason=elig_reason,
            lms_provider=s.lms_provider,
            is_simulated=(s.lms_provider == "sandbox"),
            enrollment_status="NOT_ENROLLED",
            required_hours=Decimal(f"{s.lms_required_hours:.2f}"),
            completed_hours=Decimal("0.00"),
            progress_pct=Decimal("0.00"),
            module_progress=lms_adapter.initial_module_progress(),
            exam_status="NOT_ELIGIBLE",
            certification_status="NOT_CERTIFIED",
            sync_status="IDLE",
            max_sync_attempts=s.lms_sync_max_attempts,
        )
        db.add(record)
        db.flush()
    else:
        record.eligibility_status = elig_status
        record.eligibility_reason = elig_reason
    return record


def sync_eligibility_on_kyc_approval(db: Session, app: Application) -> TrainingRecord:
    """Create or unlock the training record immediately upon KYC approval."""
    record = get_or_create_training_record(db, app)
    record.eligibility_status = "ELIGIBLE"
    record.eligibility_reason = (
        "Application has passed PolicyNest KYC checks and is eligible for 15-hour IRDAI POSP training."
    )
    db.flush()
    return record


def to_training_out(db: Session, app: Application, record: TrainingRecord) -> TrainingRecordOut:
    logs = db.scalars(
        select(LmsSyncLog)
        .where(LmsSyncLog.training_record_id == record.id)
        .order_by(desc(LmsSyncLog.occurred_at))
        .limit(15)
    ).all()
    modules = record.module_progress or lms_adapter.initial_module_progress()
    adapter_status = LmsAdapterStatusOut(**lms_adapter.get_lms_integration_status(db))
    return TrainingRecordOut(
        id=record.id,
        application_id=app.id,
        reference_code=app.reference_code,
        applicant_name=app.full_name,
        application_status=app.status,
        eligibility_status=record.eligibility_status,
        eligibility_reason=record.eligibility_reason,
        lms_provider=record.lms_provider,
        is_simulated=record.is_simulated,
        external_enrollment_id=record.external_enrollment_id,
        lms_launch_url=record.lms_launch_url,
        enrollment_status=record.enrollment_status,
        required_hours=float(record.required_hours),
        completed_hours=float(record.completed_hours),
        progress_pct=float(record.progress_pct),
        module_progress=[CurriculumModuleProgressOut(**m) for m in modules],
        enrolled_at=record.enrolled_at,
        started_at=record.started_at,
        completed_at=record.completed_at,
        exam_status=record.exam_status,
        exam_score_pct=float(record.exam_score_pct) if record.exam_score_pct is not None else None,
        exam_attempts=record.exam_attempts,
        last_exam_at=record.last_exam_at,
        next_exam_eligible_at=record.next_exam_eligible_at,
        certification_status=record.certification_status,
        certificate_number=record.certificate_number,
        certified_at=record.certified_at,
        certificate_valid_until=record.certificate_valid_until,
        sync_status=record.sync_status,
        sync_attempts=record.sync_attempts,
        max_sync_attempts=record.max_sync_attempts,
        last_sync_at=record.last_sync_at,
        next_retry_at=record.next_retry_at,
        last_error_code=record.last_error_code,
        last_error_message=record.last_error_message,
        updated_at=record.updated_at,
        adapter_status=adapter_status,
        sync_logs=[LmsSyncLogOut.model_validate(entry) for entry in logs],
    )


def _record_sync_failure(
    db: Session,
    app: Application,
    record: TrainingRecord,
    *,
    operation: str,
    result: lms_adapter.LmsSyncResult,
    request: Request | None = None,
    actor_user_id: uuid.UUID | None = None,
    actor_role: str | None = None,
) -> None:
    s = get_effective_lms_config(db)
    now = utcnow()
    record.sync_attempts = (record.sync_attempts or 0) + 1
    record.last_sync_at = now
    record.lms_provider = result.provider_name
    record.last_error_code = result.error_code
    record.last_error_message = result.error_message

    if result.origin == "UNCONFIGURED":
        record.sync_status = "NOT_CONFIGURED"
        record.next_retry_at = None
        outcome = "UNCONFIGURED"
    elif result.retryable and record.sync_attempts < record.max_sync_attempts:
        backoff_s = s.lms_sync_retry_base_seconds * (2 ** (record.sync_attempts - 1))
        record.sync_status = "RETRY_PENDING"
        record.next_retry_at = now + timedelta(seconds=backoff_s)
        outcome = "RETRY_SCHEDULED"
    else:
        record.sync_status = "ERROR"
        record.next_retry_at = None
        outcome = "FAILED"

    db.add(
        LmsSyncLog(
            training_record_id=record.id,
            application_id=app.id,
            operation=operation,
            provider_name=result.provider_name,
            adapter_origin=result.origin,
            is_simulated=result.is_simulated,
            attempt_number=record.sync_attempts,
            outcome=outcome,
            http_status=result.http_status,
            error_code=result.error_code,
            error_message=result.error_message,
            request_payload=result.request_payload,
            response_payload=result.response_payload,
            occurred_at=now,
        )
    )
    actor_user = db.get(User, actor_user_id) if actor_user_id else None
    audit.add(
        db,
        request,
        f"training.{operation.lower()}",
        outcome=audit.FAILURE,
        actor=actor_user,
        resource_type="training_record",
        resource_id=str(record.id),
        details={
            "application_id": str(app.id),
            "reference_code": app.reference_code,
            "sync_status": record.sync_status,
            "error_code": result.error_code,
            "attempt": record.sync_attempts,
        },
    )


def _apply_sync_success(
    db: Session,
    app: Application,
    record: TrainingRecord,
    *,
    operation: str,
    result: lms_adapter.LmsSyncResult,
    request: Request | None = None,
    actor_user_id: uuid.UUID | None = None,
    actor_role: str | None = None,
) -> None:
    s = get_effective_lms_config(db)
    now = utcnow()
    req_hours = float(record.required_hours or s.lms_required_hours)

    if result.external_enrollment_id:
        record.external_enrollment_id = result.external_enrollment_id
    if result.lms_launch_url:
        record.lms_launch_url = result.lms_launch_url
    record.lms_provider = result.provider_name
    record.is_simulated = result.is_simulated

    if record.enrolled_at is None:
        record.enrolled_at = now

    completed_hours = (
        float(result.completed_hours) if result.completed_hours is not None else float(record.completed_hours)
    )
    completed_hours = max(0.0, round(completed_hours, 2))
    record.completed_hours = Decimal(f"{completed_hours:.2f}")
    pct = min(100.0, round((completed_hours / req_hours) * 100.0, 2)) if req_hours > 0 else 0.0
    record.progress_pct = Decimal(f"{pct:.2f}")

    if result.module_progress:
        record.module_progress = result.module_progress
    else:
        record.module_progress = lms_adapter.distribute_module_hours(completed_hours)

    if completed_hours > 0 and record.started_at is None:
        record.started_at = now

    # Deterministic IRDAI 15-hour training completion check
    incoming_status = result.enrollment_status or record.enrollment_status
    if completed_hours >= req_hours:
        record.enrollment_status = "COMPLETED"
        if record.completed_at is None:
            record.completed_at = now
        if record.exam_status == "NOT_ELIGIBLE":
            record.exam_status = "ELIGIBLE"
    elif completed_hours > 0:
        record.enrollment_status = "IN_PROGRESS"
    else:
        record.enrollment_status = (
            "ENROLLED" if incoming_status in ("ENROLLED", "IN_PROGRESS", "COMPLETED") else incoming_status
        )

    # Deterministic IRDAI exam & certification guards (cannot certify with < 15h or < 50%)
    incoming_exam_status = result.exam_status
    incoming_score = result.exam_score_pct
    if result.exam_attempts is not None:
        record.exam_attempts = max(record.exam_attempts, int(result.exam_attempts))
    if incoming_score is not None:
        record.exam_score_pct = Decimal(f"{float(incoming_score):.2f}")
        record.last_exam_at = now

    if incoming_exam_status in ("FAILED", "COOLDOWN") or (
        incoming_score is not None and float(incoming_score) < s.lms_passing_score_pct
    ):
        record.exam_status = "COOLDOWN"
        record.next_exam_eligible_at = result.next_exam_eligible_at or (
            now + timedelta(hours=s.lms_exam_cooldown_hours)
        )
    elif incoming_exam_status == "PASSED" or result.certification_status == "CERTIFIED":
        score_val = float(record.exam_score_pct) if record.exam_score_pct is not None else 0.0
        if completed_hours < req_hours or score_val < s.lms_passing_score_pct:
            record.sync_status = "ERROR"
            record.last_error_code = "IRDAI_CERTIFICATION_GUARD_FAILED"
            record.last_error_message = (
                f"IRDAI compliance requires >= {req_hours:.1f} training hours and >= {s.lms_passing_score_pct:.0f}% "
                f"exam score before certification (received {completed_hours:.1f}h, score {score_val:.1f}%)."
            )
            db.add(
                LmsSyncLog(
                    training_record_id=record.id,
                    application_id=app.id,
                    operation=operation,
                    provider_name=result.provider_name,
                    adapter_origin=result.origin,
                    is_simulated=result.is_simulated,
                    attempt_number=max(1, record.sync_attempts),
                    outcome="FAILED",
                    http_status=result.http_status,
                    error_code=record.last_error_code,
                    error_message=record.last_error_message,
                    request_payload=result.request_payload,
                    response_payload=result.response_payload,
                    occurred_at=now,
                )
            )
            return

        record.exam_status = "PASSED"
        record.next_exam_eligible_at = None
        record.certification_status = "CERTIFIED"
        cert_at = result.certified_at or now
        record.certified_at = record.certified_at or cert_at
        record.certificate_valid_until = record.certified_at + timedelta(days=365 * s.lms_certificate_validity_years)
        if result.certificate_number:
            record.certificate_number = result.certificate_number
        elif not record.certificate_number:
            prefix = "SBX-CERT" if result.is_simulated else "PN-POSP"
            record.certificate_number = f"{prefix}-{app.reference_code}"
    elif incoming_exam_status and completed_hours >= req_hours:
        record.exam_status = incoming_exam_status

    record.sync_status = "SYNCED"
    record.sync_attempts = 0
    record.last_sync_at = now
    record.next_retry_at = None
    record.last_error_code = None
    record.last_error_message = None

    # Synchronize overall application lifecycle status cleanly
    prev_app_status = app.status
    if record.certification_status == "CERTIFIED" and app.status != "CERTIFIED":
        app.status = "CERTIFIED"
        app.last_saved_at = now
        db.add(
            ApplicationEvent(
                application_id=app.id,
                actor_user_id=actor_user_id,
                actor_role=actor_role or "SYSTEM",
                event_type="POSP_CERTIFIED",
                from_status=prev_app_status,
                to_status="CERTIFIED",
                summary=f"POSP Certificate {record.certificate_number} issued after 15h training and exam pass.",
                details={
                    "certificate_number": record.certificate_number,
                    "exam_score_pct": float(record.exam_score_pct or 0),
                    "completed_hours": float(record.completed_hours),
                    "is_simulated": record.is_simulated,
                },
            )
        )
        create_notification(
            db,
            user_id=app.user_id,
            application_id=app.id,
            category="TRAINING",
            title=f"POSP Certification Issued · {app.reference_code}",
            body=(
                f"Congratulations! Certificate {record.certificate_number} has been synchronized from the LMS."
                + (" (Non-production sandbox LMS)" if record.is_simulated else "")
            ),
            action_url=f"/app/applications/{app.id}",
        )
    elif app.status == "KYC_APPROVED" and record.enrollment_status in ("ENROLLED", "IN_PROGRESS", "COMPLETED"):
        app.status = "TRAINING_IN_PROGRESS"
        app.last_saved_at = now
        db.add(
            ApplicationEvent(
                application_id=app.id,
                actor_user_id=actor_user_id,
                actor_role=actor_role or "SYSTEM",
                event_type="LMS_ENROLLED",
                from_status=prev_app_status,
                to_status="TRAINING_IN_PROGRESS",
                summary=f"Enrolled in IRDAI 15-hour POSP curriculum ({record.external_enrollment_id}).",
                details={
                    "external_enrollment_id": record.external_enrollment_id,
                    "lms_provider": record.lms_provider,
                    "is_simulated": record.is_simulated,
                },
            )
        )
        create_notification(
            db,
            user_id=app.user_id,
            application_id=app.id,
            category="TRAINING",
            title=f"POSP 15-Hour Training Unlocked · {app.reference_code}",
            body="Your LMS training enrollment is active. Complete all 15 hours and pass the exam for POSP certification.",
            action_url=f"/app/applications/{app.id}",
        )

    db.add(
        LmsSyncLog(
            training_record_id=record.id,
            application_id=app.id,
            operation=operation,
            provider_name=result.provider_name,
            adapter_origin=result.origin,
            is_simulated=result.is_simulated,
            attempt_number=1,
            outcome="SUCCESS",
            http_status=result.http_status,
            request_payload=result.request_payload,
            response_payload=result.response_payload,
            occurred_at=now,
        )
    )
    actor_user = db.get(User, actor_user_id) if actor_user_id else None
    audit.add(
        db,
        request,
        f"training.{operation.lower()}",
        outcome=audit.SUCCESS,
        actor=actor_user,
        resource_type="training_record",
        resource_id=str(record.id),
        details={
            "application_id": str(app.id),
            "reference_code": app.reference_code,
            "enrollment_status": record.enrollment_status,
            "certification_status": record.certification_status,
            "is_simulated": record.is_simulated,
        },
    )


def enroll_in_training(
    db: Session,
    app: Application,
    auth: AuthContext,
    request: Request,
) -> TrainingRecordOut:
    record = get_or_create_training_record(db, app)
    elig_status, elig_reason = evaluate_eligibility(app)
    if elig_status != "ELIGIBLE":
        raise AppError(409, "INELIGIBLE_FOR_TRAINING", elig_reason)

    result = lms_adapter.enroll_applicant(app, record, db=db)
    if result.ok:
        _apply_sync_success(
            db,
            app,
            record,
            operation="ENROLL",
            result=result,
            request=request,
            actor_user_id=auth.user.id,
            actor_role=auth.user.role.code,
        )
    else:
        _record_sync_failure(
            db,
            app,
            record,
            operation="ENROLL",
            result=result,
            request=request,
            actor_user_id=auth.user.id,
            actor_role=auth.user.role.code,
        )
    db.commit()
    db.refresh(record)
    return to_training_out(db, app, record)


def sync_training_status(
    db: Session,
    app: Application,
    auth: AuthContext | None,
    request: Request | None,
    *,
    sandbox_action: str | None = None,
    is_retry: bool = False,
) -> TrainingRecordOut:
    record = get_or_create_training_record(db, app)
    elig_status, elig_reason = evaluate_eligibility(app)
    if elig_status != "ELIGIBLE":
        raise AppError(409, "INELIGIBLE_FOR_TRAINING", elig_reason)

    operation = "RETRY_SYNC" if is_retry else "STATUS_SYNC"
    if not record.external_enrollment_id and sandbox_action != "SIMULATE_SYNC_ERROR":
        result = lms_adapter.enroll_applicant(app, record, db=db)
        if not result.ok:
            _record_sync_failure(
                db,
                app,
                record,
                operation=operation,
                result=result,
                request=request,
                actor_user_id=auth.user.id if auth else None,
                actor_role=auth.user.role.code if auth else "SYSTEM",
            )
            db.commit()
            db.refresh(record)
            return to_training_out(db, app, record)
        _apply_sync_success(
            db,
            app,
            record,
            operation="ENROLL",
            result=result,
            request=request,
            actor_user_id=auth.user.id if auth else None,
            actor_role=auth.user.role.code if auth else "SYSTEM",
        )
        if not sandbox_action:
            db.commit()
            db.refresh(record)
            return to_training_out(db, app, record)

    result = lms_adapter.fetch_training_status(app, record, sandbox_action=sandbox_action, db=db)
    if result.ok:
        _apply_sync_success(
            db,
            app,
            record,
            operation=operation,
            result=result,
            request=request,
            actor_user_id=auth.user.id if auth else None,
            actor_role=auth.user.role.code if auth else "SYSTEM",
        )
    else:
        _record_sync_failure(
            db,
            app,
            record,
            operation=operation,
            result=result,
            request=request,
            actor_user_id=auth.user.id if auth else None,
            actor_role=auth.user.role.code if auth else "SYSTEM",
        )
    db.commit()
    db.refresh(record)
    return to_training_out(db, app, record)


def process_inbound_webhook(
    db: Session,
    payload: LmsWebhookPayload,
    request: Request,
) -> TrainingRecordOut:
    if payload.external_enrollment_id:
        record = db.scalar(
            select(TrainingRecord).where(TrainingRecord.external_enrollment_id == payload.external_enrollment_id)
        )
        app = db.get(Application, record.application_id) if record else None
    elif payload.reference_code:
        app = db.scalar(select(Application).where(Application.reference_code == payload.reference_code.strip().upper()))
        record = get_or_create_training_record(db, app) if app else None
    else:
        raise AppError(400, "INVALID_WEBHOOK_PAYLOAD", "external_enrollment_id or reference_code is required.")

    if app is None or record is None:
        raise AppError(404, "TRAINING_RECORD_NOT_FOUND", "No matching onboarding application/training record found.")

    elig_status, elig_reason = evaluate_eligibility(app)
    if elig_status != "ELIGIBLE":
        raise AppError(409, "INELIGIBLE_FOR_TRAINING", elig_reason)

    s = get_effective_lms_config(db)
    result = lms_adapter.LmsSyncResult(
        ok=True,
        provider_name=s.lms_provider if s.lms_provider != "not_configured" else "external_webhook",
        origin="WEBHOOK",
        is_simulated=False,
        http_status=200,
        external_enrollment_id=payload.external_enrollment_id or record.external_enrollment_id,
        enrollment_status=payload.enrollment_status,
        completed_hours=payload.completed_hours,
        module_progress=[m.model_dump() for m in payload.module_progress] if payload.module_progress else None,
        exam_status=payload.exam_status,
        exam_score_pct=payload.exam_score_pct,
        exam_attempts=payload.exam_attempts,
        certification_status="CERTIFIED" if payload.certificate_number else None,
        certificate_number=payload.certificate_number,
        certified_at=payload.certified_at,
        request_payload={"event_id": payload.event_id},
        response_payload=payload.model_dump(mode="json", exclude_none=True),
    )
    _apply_sync_success(db, app, record, operation="WEBHOOK_EVENT", result=result, request=request)
    db.commit()
    db.refresh(record)
    return to_training_out(db, app, record)


def list_training_overview(
    db: Session,
    auth: AuthContext,
    *,
    q: str | None = None,
    sync_status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> TrainingOverviewOut:
    scoped_apps = select(Application).where(Application.sensitivity <= auth.user.clearance_level)
    if auth.user.role.code in (RoleCode.REVIEWER, RoleCode.SENIOR_REVIEWER) and auth.user.region not in (None, "ALL"):
        scoped_apps = scoped_apps.where(Application.region == auth.user.region)

    eligible_apps = db.scalars(
        scoped_apps.where(Application.status.in_(tuple(ELIGIBLE_APP_STATUSES))).order_by(Application.updated_at.desc())
    ).all()

    # Ensure every eligible application has a TrainingRecord row so ops pipeline KPIs reflect reality
    for app in eligible_apps:
        get_or_create_training_record(db, app)
    if eligible_apps:
        db.commit()

    base_stmt = (
        select(TrainingRecord, Application)
        .join(Application, TrainingRecord.application_id == Application.id)
        .where(Application.status.in_(tuple(ELIGIBLE_APP_STATUSES)))
        .where(Application.sensitivity <= auth.user.clearance_level)
    )
    if auth.user.role.code in (RoleCode.REVIEWER, RoleCode.SENIOR_REVIEWER) and auth.user.region not in (None, "ALL"):
        base_stmt = base_stmt.where(Application.region == auth.user.region)

    all_rows = db.execute(base_stmt).all()
    kyc_awaiting = sum(1 for r, a in all_rows if a.status == "KYC_APPROVED")
    in_progress = sum(
        1 for r, a in all_rows if a.status == "TRAINING_IN_PROGRESS" and r.enrollment_status != "COMPLETED"
    )
    awaiting_exam = sum(
        1 for r, a in all_rows if r.enrollment_status == "COMPLETED" and r.certification_status != "CERTIFIED"
    )
    certified_count = sum(1 for r, a in all_rows if a.status == "CERTIFIED" or r.certification_status == "CERTIFIED")
    retry_pending = sum(1 for r, _ in all_rows if r.sync_status == "RETRY_PENDING")
    sync_err = sum(1 for r, _ in all_rows if r.sync_status in ("ERROR", "NOT_CONFIGURED"))

    filtered = base_stmt
    if q and q.strip():
        like = f"%{q.strip()}%"
        filtered = filtered.where(
            or_(
                Application.reference_code.ilike(like),
                Application.full_name.ilike(like),
                TrainingRecord.certificate_number.ilike(like),
            )
        )
    if sync_status and sync_status != "ALL":
        filtered = filtered.where(TrainingRecord.sync_status == sync_status)

    total = db.scalar(select(func.count()).select_from(filtered.subquery())) or 0
    rows = db.execute(
        filtered.order_by(desc(TrainingRecord.updated_at)).offset((page - 1) * page_size).limit(page_size)
    ).all()

    items = [
        TrainingQueueItemOut(
            application_id=app.id,
            reference_code=app.reference_code,
            applicant_name=app.full_name,
            region=app.region,
            application_status=app.status,
            eligibility_status=rec.eligibility_status,
            enrollment_status=rec.enrollment_status,
            completed_hours=float(rec.completed_hours),
            required_hours=float(rec.required_hours),
            progress_pct=float(rec.progress_pct),
            exam_status=rec.exam_status,
            exam_score_pct=float(rec.exam_score_pct) if rec.exam_score_pct is not None else None,
            certification_status=rec.certification_status,
            certificate_number=rec.certificate_number,
            sync_status=rec.sync_status,
            sync_attempts=rec.sync_attempts,
            next_retry_at=rec.next_retry_at,
            last_error_code=rec.last_error_code,
            last_error_message=rec.last_error_message,
            is_simulated=rec.is_simulated,
            updated_at=rec.updated_at,
        )
        for rec, app in rows
    ]

    return TrainingOverviewOut(
        adapter_status=LmsAdapterStatusOut(**lms_adapter.get_lms_integration_status(db)),
        kyc_approved_awaiting_training=kyc_awaiting,
        training_in_progress_count=in_progress,
        training_completed_awaiting_exam=awaiting_exam,
        certified_count=certified_count,
        sync_retry_pending_count=retry_pending,
        sync_error_count=sync_err,
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, ceil(total / page_size)) if total else 1,
    )


def retry_pending_syncs(db: Session, auth: AuthContext, request: Request) -> BatchRetryOut:
    stmt = (
        select(TrainingRecord, Application)
        .join(Application, TrainingRecord.application_id == Application.id)
        .where(TrainingRecord.sync_status.in_(("RETRY_PENDING", "ERROR", "NOT_CONFIGURED")))
        .where(Application.status.in_(tuple(ELIGIBLE_APP_STATUSES)))
        .where(Application.sensitivity <= auth.user.clearance_level)
    )
    if auth.user.role.code in (RoleCode.REVIEWER, RoleCode.SENIOR_REVIEWER) and auth.user.region not in (None, "ALL"):
        stmt = stmt.where(Application.region == auth.user.region)

    rows = db.execute(stmt.limit(50)).all()
    attempted = len(rows)
    succeeded = 0
    failed = 0
    for _rec, app in rows:
        out = sync_training_status(db, app, auth, request, is_retry=True)
        if out.sync_status == "SYNCED":
            succeeded += 1
        else:
            failed += 1
    return BatchRetryOut(
        attempted=attempted,
        succeeded=succeeded,
        failed=failed,
        message=f"Retried {attempted} training sync record(s): {succeeded} succeeded, {failed} still failing/unconfigured.",
    )
