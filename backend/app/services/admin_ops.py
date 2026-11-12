"""Phase 7 Administrator Operations service (dashboard, workloads, RBAC customization, config store)."""

import uuid

from fastapi import Request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, aliased

from app.api.routes.admin import _email_integration, _storage_integration, admin_stats
from app.core.config import get_settings
from app.core.errors import AppError
from app.models import (
    Application,
    ApplicationDecision,
    ApplicationEvent,
    DocumentFieldCorrection,
    Permission,
    Role,
    SystemConfig,
    TrainingRecord,
    User,
)
from app.models.base import utcnow
from app.rbac.catalog import RoleCode
from app.schemas.admin import (
    AdminApplicationItemOut,
    AdminApplicationPageOut,
    AdminAssignReviewerRequest,
    AdminConfigBundleOut,
    AdminDashboardOut,
    IntegrationProbeOut,
    IntegrationsConfigOut,
    IntegrationsMonitorOut,
    IntegrationStatus,
    LmsConfigOut,
    PlatformConfigOut,
    ReassignWorkloadOut,
    ReassignWorkloadRequest,
    ReviewerWorkloadOut,
    RoleDetailOut,
    SmsRetryOut,
    UpdateIntegrationsConfigRequest,
    UpdateLmsConfigRequest,
    UpdatePlatformConfigRequest,
    UpdateRolePermissionsRequest,
)
from app.services import audit, integration_health, platform_config, sms

ACTIVE_QUEUE_STATUSES = ("SUBMITTED", "IN_REVIEW", "NEEDS_MORE_INFO", "REWORK_SUBMITTED")
ADMIN_FORBIDDEN_DECISION_PERMS = {
    "application:decide",
    "application:decide_escalated",
    "fraud:review",
    "application:escalate",
}
ADMIN_CORE_PERMS = {
    "profile:read",
    "profile:update",
    "users:read",
    "users:manage",
    "roles:read",
    "audit:read",
    "system:read",
    "config:manage",
}


def _collect_integrations(db: Session) -> list[IntegrationStatus]:
    return [_email_integration(), _storage_integration()] + [
        IntegrationStatus(**st) for st in integration_health.collect_all_integration_statuses(db)
    ]


def get_admin_dashboard(db: Session) -> AdminDashboardOut:
    stats = admin_stats(db)
    by_status = dict(db.execute(select(Application.status, func.count()).group_by(Application.status)).all())
    total_apps = sum(by_status.values())
    escalated_apps = (
        db.scalar(
            select(func.count())
            .select_from(Application)
            .where(Application.escalated_at.is_not(None), Application.status.in_(ACTIVE_QUEUE_STATUSES))
        )
        or 0
    )
    certified_count = (
        db.scalar(
            select(func.count()).select_from(TrainingRecord).where(TrainingRecord.certification_status == "CERTIFIED")
        )
        or 0
    )
    sync_failed_count = (
        db.scalar(
            select(func.count())
            .select_from(TrainingRecord)
            .where(TrainingRecord.sync_status.in_(["FAILED", "RETRY_PENDING"]))
        )
        or 0
    )
    staff_counts = dict(
        db.execute(
            select(Role.code, func.count(User.id))
            .join(Role, User.role_id == Role.id)
            .where(User.is_active.is_(True), Role.code.in_([RoleCode.REVIEWER.value, RoleCode.SENIOR_REVIEWER.value]))
            .group_by(Role.code)
        ).all()
    )
    return AdminDashboardOut(
        stats=stats,
        total_applications=total_apps,
        applications_by_status=by_status,
        escalated_applications=escalated_apps,
        training_certified_count=certified_count,
        training_sync_failed_count=sync_failed_count,
        integrations=_collect_integrations(db),
        reviewer_count=staff_counts.get(RoleCode.REVIEWER.value, 0),
        senior_reviewer_count=staff_counts.get(RoleCode.SENIOR_REVIEWER.value, 0),
    )


def list_reviewers_workload(
    db: Session, *, region: str | None = None, role_filter: str | None = None
) -> list[ReviewerWorkloadOut]:
    stmt = (
        select(User)
        .join(Role, User.role_id == Role.id)
        .where(Role.code.in_([RoleCode.REVIEWER.value, RoleCode.SENIOR_REVIEWER.value]))
    )
    if region:
        stmt = stmt.where(User.region == region)
    if role_filter:
        stmt = stmt.where(Role.code == role_filter)

    reviewers = db.scalars(stmt.order_by(Role.code.desc(), User.full_name.asc())).all()
    if not reviewers:
        return []

    reviewer_ids = [r.id for r in reviewers]

    active_assigned = dict(
        db.execute(
            select(Application.assigned_reviewer_id, func.count())
            .where(
                Application.assigned_reviewer_id.in_(reviewer_ids),
                Application.status.in_(ACTIVE_QUEUE_STATUSES),
            )
            .group_by(Application.assigned_reviewer_id)
        ).all()
    )
    escalated_assigned = dict(
        db.execute(
            select(Application.assigned_reviewer_id, func.count())
            .where(
                Application.assigned_reviewer_id.in_(reviewer_ids),
                Application.status.in_(ACTIVE_QUEUE_STATUSES),
                Application.escalated_at.is_not(None),
            )
            .group_by(Application.assigned_reviewer_id)
        ).all()
    )
    decision_rows = db.execute(
        select(
            ApplicationDecision.decided_by_user_id,
            func.count(),
            func.count().filter(ApplicationDecision.is_override.is_(True)),
        )
        .where(ApplicationDecision.decided_by_user_id.in_(reviewer_ids))
        .group_by(ApplicationDecision.decided_by_user_id)
    ).all()
    decisions_map = {uid: total for uid, total, _ in decision_rows}
    overrides_map = {uid: ov for uid, _, ov in decision_rows}
    corrections_map = dict(
        db.execute(
            select(DocumentFieldCorrection.corrected_by_user_id, func.count())
            .where(DocumentFieldCorrection.corrected_by_user_id.in_(reviewer_ids))
            .group_by(DocumentFieldCorrection.corrected_by_user_id)
        ).all()
    )

    return [
        ReviewerWorkloadOut(
            id=u.id,
            email=u.email,
            full_name=u.full_name,
            role=RoleCode(u.role.code),
            region=u.region,
            clearance_level=u.clearance_level,
            is_active=u.is_active,
            email_verified=u.email_verified_at is not None,
            active_assigned_count=int(active_assigned.get(u.id, 0)),
            escalated_assigned_count=int(escalated_assigned.get(u.id, 0)),
            decisions_made_count=int(decisions_map.get(u.id, 0)),
            overrides_count=int(overrides_map.get(u.id, 0)),
            corrections_requested_count=int(corrections_map.get(u.id, 0)),
            last_login_at=u.last_login_at,
        )
        for u in reviewers
    ]


def _validate_target_reviewer(db: Session, target_id: uuid.UUID | None, *, require_senior: bool = False) -> User | None:
    if target_id is None:
        return None
    target = db.get(User, target_id)
    if target is None:
        raise AppError(status_code=404, code="REVIEWER_NOT_FOUND", message="Target reviewer not found.")
    if not target.is_active:
        raise AppError(status_code=400, code="REVIEWER_INACTIVE", message="Target reviewer account is inactive.")
    if target.role.code not in {RoleCode.REVIEWER.value, RoleCode.SENIOR_REVIEWER.value}:
        raise AppError(
            status_code=400,
            code="INVALID_REVIEWER_ROLE",
            message="Applications can only be assigned to REVIEWER or SENIOR_REVIEWER accounts.",
        )
    if require_senior and target.role.code != RoleCode.SENIOR_REVIEWER.value:
        raise AppError(
            status_code=400,
            code="SENIOR_REVIEWER_REQUIRED",
            message="Escalated applications must be assigned to an active Senior Reviewer.",
        )
    return target


def reassign_reviewer_workload(
    db: Session,
    request: Request,
    *,
    source_user_id: uuid.UUID,
    body: ReassignWorkloadRequest,
    actor: User,
) -> ReassignWorkloadOut:
    source = db.get(User, source_user_id)
    if source is None:
        raise AppError(status_code=404, code="REVIEWER_NOT_FOUND", message="Source reviewer not found.")
    if source.role.code not in {RoleCode.REVIEWER.value, RoleCode.SENIOR_REVIEWER.value}:
        raise AppError(status_code=400, code="INVALID_REVIEWER_ROLE", message="User is not a reviewer.")
    if body.target_reviewer_id == source.id:
        raise AppError(status_code=400, code="SAME_REVIEWER", message="Source and target reviewer cannot be the same.")

    active_apps = db.scalars(
        select(Application).where(
            Application.assigned_reviewer_id == source.id,
            Application.status.in_(ACTIVE_QUEUE_STATUSES),
        )
    ).all()

    has_escalated = any(app.escalated_at is not None for app in active_apps)
    target = _validate_target_reviewer(db, body.target_reviewer_id, require_senior=has_escalated)

    now = utcnow()
    for app in active_apps:
        app.assigned_reviewer_id = target.id if target else None
        app.assigned_at = now if target else None
        db.add(
            ApplicationEvent(
                application_id=app.id,
                actor_user_id=actor.id,
                actor_role=actor.role.code,
                event_type="ADMIN_WORKLOAD_REASSIGNED",
                from_status=app.status,
                to_status=app.status,
                summary=(
                    f"Admin reassigned workload from {source.email} to {target.email}"
                    if target
                    else f"Admin returned application to unassigned queue from {source.email}"
                ),
                details={
                    "source_reviewer_id": str(source.id),
                    "target_reviewer_id": str(target.id) if target else None,
                    "reason": body.reason.strip(),
                },
            )
        )

    audit.add(
        db,
        request,
        "admin.reviewer.reassign_workload",
        actor=actor,
        resource_type="user",
        resource_id=str(source.id),
        details={
            "source_email": source.email,
            "target_reviewer_id": str(target.id) if target else None,
            "target_email": target.email if target else None,
            "reassigned_count": len(active_apps),
            "reason": body.reason.strip(),
        },
    )
    db.commit()
    return ReassignWorkloadOut(
        source_reviewer_id=source.id,
        target_reviewer_id=target.id if target else None,
        reassigned_count=len(active_apps),
    )


def _to_admin_app_item(
    app: Application, applicant: User, reviewer: User | None, tr: TrainingRecord | None
) -> AdminApplicationItemOut:
    return AdminApplicationItemOut(
        id=app.id,
        reference_code=app.reference_code,
        applicant_id=applicant.id,
        applicant_name=app.full_name or applicant.full_name,
        applicant_email=applicant.email,
        status=app.status,
        region=app.region,
        assigned_reviewer_id=reviewer.id if reviewer else None,
        assigned_reviewer_name=reviewer.full_name if reviewer else None,
        assigned_reviewer_email=reviewer.email if reviewer else None,
        is_escalated=app.escalated_at is not None,
        fraud_flag=app.fraud_flag,
        training_status=tr.certification_status if tr else None,
        submitted_at=app.submitted_at,
        updated_at=app.updated_at,
    )


def list_admin_applications(
    db: Session,
    *,
    q: str | None = None,
    status_filter: str | None = None,
    region: str | None = None,
    escalated_only: bool = False,
    unassigned_only: bool = False,
    page: int = 1,
    page_size: int = 25,
) -> AdminApplicationPageOut:
    Applicant = aliased(User)
    Reviewer = aliased(User)

    counts_by_status = dict(db.execute(select(Application.status, func.count()).group_by(Application.status)).all())

    stmt = (
        select(Application, Applicant, Reviewer, TrainingRecord)
        .join(Applicant, Application.user_id == Applicant.id)
        .outerjoin(Reviewer, Application.assigned_reviewer_id == Reviewer.id)
        .outerjoin(TrainingRecord, TrainingRecord.application_id == Application.id)
    )
    if status_filter:
        stmt = stmt.where(Application.status == status_filter)
    if region:
        stmt = stmt.where(Application.region == region)
    if escalated_only:
        stmt = stmt.where(Application.escalated_at.is_not(None))
    if unassigned_only:
        stmt = stmt.where(Application.assigned_reviewer_id.is_(None))
    if q and q.strip():
        needle = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Application.reference_code.ilike(needle),
                Application.full_name.ilike(needle),
                Applicant.full_name.ilike(needle),
                Applicant.email.ilike(needle),
            )
        )

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.execute(
        stmt.order_by(Application.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    items = [_to_admin_app_item(app, applicant, reviewer, tr) for app, applicant, reviewer, tr in rows]
    return AdminApplicationPageOut(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        counts_by_status=counts_by_status,
    )


def assign_application_reviewer(
    db: Session,
    request: Request,
    *,
    application_id: uuid.UUID,
    body: AdminAssignReviewerRequest,
    actor: User,
) -> AdminApplicationItemOut:
    app = db.get(Application, application_id)
    if app is None:
        raise AppError(status_code=404, code="APPLICATION_NOT_FOUND", message="Application not found.")
    if body.reviewer_id is not None and body.reviewer_id == app.user_id:
        raise AppError(
            status_code=400,
            code="CONFLICT_OF_INTEREST",
            message="An applicant cannot be assigned to review their own application.",
        )
    target = _validate_target_reviewer(db, body.reviewer_id, require_senior=app.escalated_at is not None)
    previous_reviewer_id = app.assigned_reviewer_id
    app.assigned_reviewer_id = target.id if target else None
    app.assigned_at = utcnow() if target else None

    db.add(
        ApplicationEvent(
            application_id=app.id,
            actor_user_id=actor.id,
            actor_role=actor.role.code,
            event_type="ADMIN_ASSIGNED_REVIEWER",
            from_status=app.status,
            to_status=app.status,
            summary=(
                f"Administrator assigned reviewer {target.email}"
                if target
                else "Administrator cleared reviewer assignment"
            ),
            details={
                "previous_reviewer_id": str(previous_reviewer_id) if previous_reviewer_id else None,
                "new_reviewer_id": str(target.id) if target else None,
                "reason": body.reason.strip(),
            },
        )
    )
    audit.add(
        db,
        request,
        "admin.application.assign_reviewer",
        actor=actor,
        resource_type="application",
        resource_id=str(app.id),
        details={
            "reference_code": app.reference_code,
            "previous_reviewer_id": str(previous_reviewer_id) if previous_reviewer_id else None,
            "new_reviewer_id": str(target.id) if target else None,
            "new_reviewer_email": target.email if target else None,
            "reason": body.reason.strip(),
        },
    )
    db.commit()

    applicant = db.get(User, app.user_id)
    tr = db.scalar(select(TrainingRecord).where(TrainingRecord.application_id == app.id))
    return _to_admin_app_item(app, applicant, target, tr)


def update_role_permissions(
    db: Session,
    request: Request,
    *,
    role_code: str,
    body: UpdateRolePermissionsRequest,
    actor: User,
) -> RoleDetailOut:
    role = db.scalar(select(Role).where(Role.code == role_code))
    if role is None:
        raise AppError(status_code=404, code="ROLE_NOT_FOUND", message=f"Role '{role_code}' not found.")
    if role.code == RoleCode.APPLICANT.value:
        raise AppError(
            status_code=400,
            code="ROLE_PROTECTED",
            message="The APPLICANT role permissions cannot be modified.",
        )

    requested = set(body.permission_codes)
    all_perms = db.scalars(select(Permission)).all()
    perms_by_code = {p.code: p for p in all_perms}
    unknown = requested - perms_by_code.keys()
    if unknown:
        raise AppError(
            status_code=400,
            code="UNKNOWN_PERMISSION",
            message=f"Unknown permission code(s): {', '.join(sorted(unknown))}",
        )

    if role.code == RoleCode.ADMIN.value:
        forbidden = requested & ADMIN_FORBIDDEN_DECISION_PERMS
        if forbidden:
            raise AppError(
                status_code=400,
                code="SEPARATION_OF_DUTIES",
                message=(
                    "Separation of Duties prohibits granting case decision or fraud adjudication permissions "
                    f"to ADMIN: {', '.join(sorted(forbidden))}"
                ),
            )
        missing_core = ADMIN_CORE_PERMS - requested
        if missing_core:
            raise AppError(
                status_code=400,
                code="REQUIRED_ADMIN_PERMISSION",
                message=f"Cannot strip core ADMIN permissions: {', '.join(sorted(missing_core))}",
            )
    elif "profile:read" not in requested:
        raise AppError(
            status_code=400,
            code="REQUIRED_PERMISSION",
            message="Staff roles must retain 'profile:read'.",
        )

    old_codes = set(role.permission_codes)
    role.permissions = [perms_by_code[code] for code in sorted(requested)]
    added = sorted(requested - old_codes)
    removed = sorted(old_codes - requested)

    audit.add(
        db,
        request,
        "admin.role.permissions_updated",
        actor=actor,
        resource_type="role",
        resource_id=role.code,
        details={
            "role_code": role.code,
            "added": added,
            "removed": removed,
            "reason": body.reason.strip(),
        },
    )
    db.commit()
    db.refresh(role)
    user_count = db.scalar(select(func.count()).select_from(User).where(User.role_id == role.id)) or 0
    return RoleDetailOut(
        code=RoleCode(role.code),
        name=role.name,
        description=role.description,
        is_staff=role.is_staff,
        user_count=int(user_count),
        permissions=sorted(p.code for p in role.permissions),
    )


def _forbid_sandbox_in_production(provider_map: dict[str, str]) -> None:
    if get_settings().app_env != "production":
        return
    sandbox_keys = [k for k, v in provider_map.items() if v == "sandbox"]
    if sandbox_keys:
        raise AppError(
            status_code=400,
            code="SANDBOX_FORBIDDEN_IN_PROD",
            message=f"Sandbox mode cannot be enabled in production ({', '.join(sandbox_keys)}).",
        )


def _build_lms_out(db: Session) -> LmsConfigOut:
    eff = platform_config.get_effective_lms_config(db)
    row = db.get(SystemConfig, "lms")
    return LmsConfigOut(
        lms_provider=eff.lms_provider,
        lms_api_base_url=eff.lms_api_base_url,
        lms_course_code=eff.lms_course_code,
        lms_required_hours=eff.lms_required_hours,
        lms_passing_score_pct=eff.lms_passing_score_pct,
        lms_timeout_seconds=eff.lms_timeout_seconds,
        lms_exam_cooldown_hours=eff.lms_exam_cooldown_hours,
        lms_certificate_validity_years=eff.lms_certificate_validity_years,
        lms_sync_retry_base_seconds=eff.lms_sync_retry_base_seconds,
        lms_sync_max_attempts=eff.lms_sync_max_attempts,
        has_api_key=bool(eff.lms_api_key),
        api_key_hint=platform_config.mask_secret_hint(eff.lms_api_key),
        has_webhook_secret=bool(eff.lms_webhook_secret),
        webhook_secret_hint=platform_config.mask_secret_hint(eff.lms_webhook_secret),
        source=eff.source,
        updated_at=row.updated_at if row else None,
    )


def _build_integrations_out(db: Session) -> IntegrationsConfigOut:
    eff = platform_config.get_effective_integrations_config(db)
    row = db.get(SystemConfig, "integrations")
    return IntegrationsConfigOut(
        ocr_provider=eff.ocr_provider,
        ocr_api_base_url=eff.ocr_api_base_url,
        has_ocr_api_key=bool(eff.ocr_api_key),
        ocr_api_key_hint=platform_config.mask_secret_hint(eff.ocr_api_key),
        ai_provider=eff.ai_provider,
        gemini_model=eff.gemini_model,
        has_gemini_api_key=bool(eff.gemini_api_key),
        gemini_api_key_hint=platform_config.mask_secret_hint(eff.gemini_api_key),
        ifsc_lookup_enabled=eff.ifsc_lookup_enabled,
        pan_verification_provider=eff.pan_verification_provider,
        pan_api_base_url=eff.pan_api_base_url,
        has_pan_api_key=bool(eff.pan_api_key),
        pan_api_key_hint=platform_config.mask_secret_hint(eff.pan_api_key),
        bank_verification_provider=eff.bank_verification_provider,
        bank_api_base_url=eff.bank_api_base_url,
        has_bank_api_key=bool(eff.bank_api_key),
        bank_api_key_hint=platform_config.mask_secret_hint(eff.bank_api_key),
        digilocker_provider=eff.digilocker_provider,
        digilocker_base_url=eff.digilocker_base_url,
        digilocker_client_id=eff.digilocker_client_id,
        has_digilocker_client_secret=bool(eff.digilocker_client_secret),
        digilocker_client_secret_hint=platform_config.mask_secret_hint(eff.digilocker_client_secret),
        face_match_provider=eff.face_match_provider,
        face_api_base_url=eff.face_api_base_url,
        has_face_api_key=bool(eff.face_api_key),
        face_api_key_hint=platform_config.mask_secret_hint(eff.face_api_key),
        sms_provider=eff.sms_provider,
        sms_api_base_url=eff.sms_api_base_url,
        sms_sender_id=eff.sms_sender_id,
        sms_timeout_seconds=eff.sms_timeout_seconds,
        sms_max_attempts=eff.sms_max_attempts,
        has_sms_api_key=bool(eff.sms_api_key),
        sms_api_key_hint=platform_config.mask_secret_hint(eff.sms_api_key),
        has_webhook_shared_secret=bool(eff.webhook_shared_secret),
        webhook_shared_secret_hint=platform_config.mask_secret_hint(eff.webhook_shared_secret),
        integration_http_timeout_seconds=eff.integration_http_timeout_seconds,
        integration_http_max_retries=eff.integration_http_max_retries,
        source=eff.source,
        updated_at=row.updated_at if row else None,
    )


def _build_platform_out(db: Session) -> PlatformConfigOut:
    eff = platform_config.get_effective_platform_config(db)
    row = db.get(SystemConfig, "platform")
    return PlatformConfigOut(
        public_app_url=eff.public_app_url,
        require_email_verification=eff.require_email_verification,
        session_idle_minutes=eff.session_idle_minutes,
        login_max_failures=eff.login_max_failures,
        login_lockout_minutes=eff.login_lockout_minutes,
        max_upload_size_mb=eff.max_upload_size_mb,
        source=eff.source,
        updated_at=row.updated_at if row else None,
    )


def get_config_bundle(db: Session) -> AdminConfigBundleOut:
    return AdminConfigBundleOut(
        lms=_build_lms_out(db),
        integrations=_build_integrations_out(db),
        platform=_build_platform_out(db),
        integrations_health=_collect_integrations(db),
    )


def update_lms_config(db: Session, request: Request, body: UpdateLmsConfigRequest, actor: User) -> LmsConfigOut:
    _forbid_sandbox_in_production({"lms_provider": body.lms_provider})
    base_url = body.lms_api_base_url.strip() if body.lms_api_base_url and body.lms_api_base_url.strip() else None
    if body.lms_provider == "http_api":
        if not base_url or not (base_url.startswith("http://") or base_url.startswith("https://")):
            raise AppError(
                status_code=400,
                code="LMS_BASE_URL_REQUIRED",
                message="A valid http(s) LMS API base URL is required when lms_provider is 'http_api'.",
            )

    clear_keys = []
    if body.clear_api_key:
        clear_keys.append("lms_api_key")
    if body.clear_webhook_secret:
        clear_keys.append("lms_webhook_secret")

    _, touched_secrets = platform_config.upsert_section(
        db,
        "lms",
        {
            "lms_provider": body.lms_provider,
            "lms_api_base_url": base_url,
            "lms_course_code": body.lms_course_code.strip(),
            "lms_required_hours": body.lms_required_hours,
            "lms_passing_score_pct": body.lms_passing_score_pct,
            "lms_timeout_seconds": body.lms_timeout_seconds,
            "lms_exam_cooldown_hours": body.lms_exam_cooldown_hours,
            "lms_certificate_validity_years": body.lms_certificate_validity_years,
            "lms_sync_retry_base_seconds": body.lms_sync_retry_base_seconds,
            "lms_sync_max_attempts": body.lms_sync_max_attempts,
        },
        secret_updates={"lms_api_key": body.lms_api_key, "lms_webhook_secret": body.lms_webhook_secret},
        clear_secrets=clear_keys,
        actor=actor,
    )
    audit.add(
        db,
        request,
        "admin.config.lms_updated",
        actor=actor,
        resource_type="system_config",
        resource_id="lms",
        details={
            "lms_provider": body.lms_provider,
            "lms_course_code": body.lms_course_code.strip(),
            "secrets_modified": touched_secrets,
        },
    )
    db.commit()
    return _build_lms_out(db)


def _clean_optional_url(raw: str | None, field_name: str) -> str | None:
    if raw is None:
        return None
    val = raw.strip().rstrip("/")
    if not val:
        return None
    if not (val.startswith("http://") or val.startswith("https://")):
        raise AppError(
            status_code=400,
            code="INVALID_URL",
            message=f"{field_name} must start with http:// or https://",
        )
    return val


def update_integrations_config(
    db: Session, request: Request, body: UpdateIntegrationsConfigRequest, actor: User
) -> IntegrationsConfigOut:
    _forbid_sandbox_in_production(
        {
            "pan_verification_provider": body.pan_verification_provider,
            "bank_verification_provider": body.bank_verification_provider,
            "digilocker_provider": body.digilocker_provider,
            "face_match_provider": body.face_match_provider,
            "sms_provider": body.sms_provider,
        }
    )
    clear_keys = [
        key
        for key, flag in (
            ("ocr_api_key", body.clear_ocr_api_key),
            ("gemini_api_key", body.clear_gemini_api_key),
            ("pan_api_key", body.clear_pan_api_key),
            ("bank_api_key", body.clear_bank_api_key),
            ("digilocker_client_secret", body.clear_digilocker_client_secret),
            ("face_api_key", body.clear_face_api_key),
            ("sms_api_key", body.clear_sms_api_key),
            ("webhook_shared_secret", body.clear_webhook_shared_secret),
        )
        if flag
    ]
    _, touched_secrets = platform_config.upsert_section(
        db,
        "integrations",
        {
            "ocr_provider": body.ocr_provider,
            "ocr_api_base_url": _clean_optional_url(body.ocr_api_base_url, "ocr_api_base_url"),
            "ai_provider": body.ai_provider,
            "gemini_model": body.gemini_model.strip(),
            "ifsc_lookup_enabled": body.ifsc_lookup_enabled,
            "pan_verification_provider": body.pan_verification_provider,
            "pan_api_base_url": _clean_optional_url(body.pan_api_base_url, "pan_api_base_url"),
            "bank_verification_provider": body.bank_verification_provider,
            "bank_api_base_url": _clean_optional_url(body.bank_api_base_url, "bank_api_base_url"),
            "digilocker_provider": body.digilocker_provider,
            "digilocker_base_url": _clean_optional_url(body.digilocker_base_url, "digilocker_base_url"),
            "digilocker_client_id": (body.digilocker_client_id or "").strip() or None,
            "face_match_provider": body.face_match_provider,
            "face_api_base_url": _clean_optional_url(body.face_api_base_url, "face_api_base_url"),
            "sms_provider": body.sms_provider,
            "sms_api_base_url": _clean_optional_url(body.sms_api_base_url, "sms_api_base_url"),
            "sms_sender_id": (body.sms_sender_id or "").strip() or None,
            "sms_timeout_seconds": body.sms_timeout_seconds,
            "sms_max_attempts": body.sms_max_attempts,
            "integration_http_timeout_seconds": body.integration_http_timeout_seconds,
            "integration_http_max_retries": body.integration_http_max_retries,
        },
        secret_updates={
            "ocr_api_key": body.ocr_api_key,
            "gemini_api_key": body.gemini_api_key,
            "pan_api_key": body.pan_api_key,
            "bank_api_key": body.bank_api_key,
            "digilocker_client_secret": body.digilocker_client_secret,
            "face_api_key": body.face_api_key,
            "sms_api_key": body.sms_api_key,
            "webhook_shared_secret": body.webhook_shared_secret,
        },
        clear_secrets=clear_keys,
        actor=actor,
    )
    audit.add(
        db,
        request,
        "admin.config.integrations_updated",
        actor=actor,
        resource_type="system_config",
        resource_id="integrations",
        details={
            "ocr_provider": body.ocr_provider,
            "ai_provider": body.ai_provider,
            "pan_verification_provider": body.pan_verification_provider,
            "bank_verification_provider": body.bank_verification_provider,
            "digilocker_provider": body.digilocker_provider,
            "face_match_provider": body.face_match_provider,
            "sms_provider": body.sms_provider,
            "secrets_modified": touched_secrets,
        },
    )
    db.commit()
    return _build_integrations_out(db)


def update_platform_config(
    db: Session, request: Request, body: UpdatePlatformConfigRequest, actor: User
) -> PlatformConfigOut:
    url = body.public_app_url.strip().rstrip("/")
    if not (url.startswith("http://") or url.startswith("https://")):
        raise AppError(
            status_code=400, code="INVALID_URL", message="public_app_url must start with http:// or https://"
        )

    platform_config.upsert_section(
        db,
        "platform",
        {
            "public_app_url": url,
            "require_email_verification": body.require_email_verification,
            "session_idle_minutes": body.session_idle_minutes,
            "login_max_failures": body.login_max_failures,
            "login_lockout_minutes": body.login_lockout_minutes,
            "max_upload_size_mb": body.max_upload_size_mb,
        },
        actor=actor,
    )
    audit.add(
        db,
        request,
        "admin.config.platform_updated",
        actor=actor,
        resource_type="system_config",
        resource_id="platform",
        details={
            "public_app_url": url,
            "require_email_verification": body.require_email_verification,
            "session_idle_minutes": body.session_idle_minutes,
            "login_max_failures": body.login_max_failures,
            "login_lockout_minutes": body.login_lockout_minutes,
            "max_upload_size_mb": body.max_upload_size_mb,
        },
    )
    db.commit()
    return _build_platform_out(db)


def reset_config_section(db: Session, request: Request, *, section: str, actor: User) -> AdminConfigBundleOut:
    if section not in {"lms", "integrations", "platform"}:
        raise AppError(status_code=400, code="UNKNOWN_SECTION", message=f"Invalid configuration section '{section}'.")
    deleted = platform_config.reset_section(db, section)
    audit.add(
        db,
        request,
        "admin.config.section_reset",
        actor=actor,
        resource_type="system_config",
        resource_id=section,
        details={"section": section, "had_override": deleted},
    )
    db.commit()
    return get_config_bundle(db)


def probe_integrations_action(
    db: Session, request: Request, *, actor: User, target_key: str | None = None
) -> list[IntegrationProbeOut]:
    rows = integration_health.probe_integrations(db, request, actor=actor, target_key=target_key)
    return [IntegrationProbeOut.model_validate(row) for row in rows]


def get_integrations_monitor_action(db: Session) -> IntegrationsMonitorOut:
    data = integration_health.get_integrations_monitor(db)
    return IntegrationsMonitorOut.model_validate(data)


def retry_failed_sms_action(db: Session, request: Request, *, actor: User) -> SmsRetryOut:
    result = sms.retry_failed_sms(db, limit=20)
    audit.add(
        db,
        request,
        "admin.integrations.sms_retried",
        actor=actor,
        resource_type="sms_deliveries",
        details=result,
    )
    db.commit()
    return SmsRetryOut(**result)
