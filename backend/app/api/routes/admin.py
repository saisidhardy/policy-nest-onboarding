import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, Response
from sqlalchemy import func, or_, select

from app.api.deps import DB, AuthContext, enforce_policy, require_permission
from app.api.routes.health import database_status
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import hash_password
from app.models import AuditLog, EmailDelivery, Permission, Role, User, UserSession
from app.models.base import utcnow
from app.rbac.catalog import RoleCode
from app.rbac.policy import Resource
from app.schemas.admin import (
    AdminStatsOut,
    AdminUserOut,
    AuditLogOut,
    CreateUserRequest,
    IntegrationStatus,
    PermissionOut,
    RoleDetailOut,
    RolesMatrixOut,
    SystemHealthOut,
    UpdateUserRequest,
)
from app.schemas.auth import EmailDispatchResult
from app.schemas.common import Page
from app.services import audit
from app.services.auth import PURPOSE_INVITE, issue_action_token, live_session_filter, revoke_all_sessions
from app.services.email import get_provider, queue_email
from app.services.lms_adapter import get_lms_integration_status
from app.services.sms import get_sms_integration_status
from app.services.storage import get_storage
from app.services.verification_providers import get_verification_integration_statuses, get_webhook_integration_status

router = APIRouter(prefix="/admin", tags=["admin"])

PLANNED_INTEGRATIONS: list[tuple[str, str, str]] = []


def _get_user(db: DB, user_id: uuid.UUID) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise AppError(404, "NOT_FOUND", "User not found.")
    return user


def _role(db: DB, code: RoleCode) -> Role:
    role = db.scalar(select(Role).where(Role.code == code.value))
    if role is None:
        raise AppError(400, "UNKNOWN_ROLE", "Unknown role.")
    return role


def _active_admin_count(db: DB) -> int:
    # Row locks serialise concurrent demotions/deactivations so the last-admin guard cannot be raced.
    ids = db.scalars(
        select(User.id).join(Role).where(Role.code == RoleCode.ADMIN.value, User.is_active).with_for_update(of=User)
    ).all()
    return len(ids)


@router.get("/users", response_model=Page[AdminUserOut])
def list_users(
    db: DB,
    _: AuthContext = Depends(require_permission("users:read")),
    q: str | None = Query(default=None, max_length=100),
    role: RoleCode | None = None,
    status: str | None = Query(default=None, pattern="^(active|inactive|locked|unverified|invited)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    stmt = select(User).join(Role)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(User.email.ilike(like), User.full_name.ilike(like)))
    if role:
        stmt = stmt.where(Role.code == role.value)
    now = utcnow()
    if status == "active":
        stmt = stmt.where(User.is_active)
    elif status == "inactive":
        stmt = stmt.where(User.is_active.is_(False))
    elif status == "locked":
        stmt = stmt.where(User.locked_until > now)
    elif status == "unverified":
        stmt = stmt.where(User.email_verified_at.is_(None), User.password_hash.is_not(None))
    elif status == "invited":
        stmt = stmt.where(User.password_hash.is_(None))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return Page(items=[AdminUserOut.model_validate(u) for u in rows], total=total, page=page, page_size=page_size)


@router.post("/users", response_model=AdminUserOut, status_code=201)
def create_user(
    body: CreateUserRequest,
    request: Request,
    db: DB,
    background: BackgroundTasks,
    auth: AuthContext = Depends(require_permission("users:manage")),
):
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise AppError(409, "EMAIL_ALREADY_REGISTERED", "A user with this email already exists.")

    generated_secret: str | None = None
    if body.initial_password:
        generated_secret = body.initial_password
    elif body.auto_generate_password and body.role != RoleCode.APPLICANT:
        import secrets
        import string

        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        generated_secret = "".join(secrets.choice(alphabet) for _ in range(16))

    now = utcnow()
    user = User(
        id=uuid.uuid4(),
        email=email,
        full_name=body.full_name,
        role=_role(db, body.role),
        region=body.region,
        clearance_level=body.clearance_level,
        password_hash=hash_password(generated_secret) if generated_secret else None,
        password_changed_at=now if generated_secret else None,
        email_verified_at=now if generated_secret else None,
    )
    db.add(user)
    db.flush()

    if generated_secret:
        delivery = queue_email(db, background, user, "staff_credentials", generated_secret)
        action_name = "admin.staff_provisioned"
    else:
        token = issue_action_token(db, user, PURPOSE_INVITE, timedelta(hours=get_settings().invite_ttl_hours))
        delivery = queue_email(db, background, user, "invite", token)
        action_name = "admin.user_invited"

    audit.add(
        db,
        request,
        action_name,
        actor=auth.user,
        resource_type="user",
        resource_id=str(user.id),
        details={
            "email": email,
            "role": body.role.value,
            "region": body.region,
            "clearance_level": body.clearance_level,
            "email_delivery": delivery,
            "has_secret": bool(generated_secret),
        },
    )
    out = AdminUserOut.model_validate(user)
    out.generated_secret = generated_secret
    return out


@router.patch("/users/{user_id}", response_model=AdminUserOut)
def update_user(
    user_id: uuid.UUID,
    body: UpdateUserRequest,
    request: Request,
    db: DB,
    auth: AuthContext = Depends(require_permission("users:manage")),
):
    target = _get_user(db, user_id)
    changes: dict[str, dict] = {}
    is_admin = target.role.code == RoleCode.ADMIN.value

    if body.role is not None and body.role.value != target.role.code:
        enforce_policy(
            request, auth, "users:manage", Resource(type="user", id=str(target.id), attributes={"change": "role"})
        )
        if is_admin and target.is_active and _active_admin_count(db) <= 1:
            raise AppError(409, "LAST_ADMIN", "At least one active administrator is required.")
        changes["role"] = {"from": target.role.code, "to": body.role.value}
        target.role = _role(db, body.role)
        revoke_all_sessions(db, target.id)

    if body.is_active is not None and body.is_active != target.is_active:
        enforce_policy(
            request, auth, "users:manage", Resource(type="user", id=str(target.id), attributes={"change": "is_active"})
        )
        if not body.is_active and is_admin and _active_admin_count(db) <= 1:
            raise AppError(409, "LAST_ADMIN", "At least one active administrator is required.")
        changes["is_active"] = {"from": target.is_active, "to": body.is_active}
        target.is_active = body.is_active
        if not body.is_active:
            revoke_all_sessions(db, target.id)

    if body.clear_region and target.region is not None:
        changes["region"] = {"from": target.region, "to": None}
        target.region = None
    elif body.region is not None and body.region != target.region:
        changes["region"] = {"from": target.region, "to": body.region}
        target.region = body.region

    if body.clearance_level is not None and body.clearance_level != target.clearance_level:
        changes["clearance_level"] = {"from": target.clearance_level, "to": body.clearance_level}
        target.clearance_level = body.clearance_level

    if changes:
        audit.add(
            db,
            request,
            "admin.user_updated",
            actor=auth.user,
            resource_type="user",
            resource_id=str(target.id),
            details={"changes": changes},
        )
    db.flush()
    return AdminUserOut.model_validate(target)


@router.post("/users/{user_id}/unlock", response_model=AdminUserOut)
def unlock_user(
    user_id: uuid.UUID,
    request: Request,
    db: DB,
    auth: AuthContext = Depends(require_permission("users:manage")),
):
    target = _get_user(db, user_id)
    target.locked_until = None
    target.failed_login_count = 0
    audit.add(db, request, "admin.user_unlocked", actor=auth.user, resource_type="user", resource_id=str(target.id))
    return AdminUserOut.model_validate(target)


@router.post("/users/{user_id}/resend-invite", response_model=EmailDispatchResult)
def resend_invite(
    user_id: uuid.UUID,
    request: Request,
    db: DB,
    background: BackgroundTasks,
    auth: AuthContext = Depends(require_permission("users:manage")),
):
    target = _get_user(db, user_id)
    if not target.invitation_pending:
        raise AppError(400, "NOT_INVITED", "This user has already set a password.")
    if not target.is_active:
        raise AppError(400, "ACCOUNT_DISABLED", "Activate the user before re-sending the invitation.")
    token = issue_action_token(db, target, PURPOSE_INVITE, timedelta(hours=get_settings().invite_ttl_hours))
    delivery = queue_email(db, background, target, "invite", token)
    audit.add(
        db,
        request,
        "admin.invite_resent",
        actor=auth.user,
        resource_type="user",
        resource_id=str(target.id),
        details={"email_delivery": delivery},
    )
    return EmailDispatchResult(message="Invitation re-sent.", email_delivery=delivery)


@router.get("/roles", response_model=RolesMatrixOut)
def roles_matrix(db: DB, _: AuthContext = Depends(require_permission("roles:read"))):
    counts = dict(db.execute(select(User.role_id, func.count()).group_by(User.role_id)).all())
    roles = db.scalars(select(Role).order_by(Role.id)).all()
    perms = db.scalars(select(Permission).order_by(Permission.category, Permission.code)).all()
    return RolesMatrixOut(
        roles=[
            RoleDetailOut(
                code=r.code,
                name=r.name,
                description=r.description,
                is_staff=r.is_staff,
                user_count=counts.get(r.id, 0),
                permissions=sorted(r.permission_codes),
            )
            for r in roles
        ],
        permissions=[PermissionOut.model_validate(p) for p in perms],
    )


@router.get("/audit-logs", response_model=Page[AuditLogOut])
def audit_logs(
    db: DB,
    _: AuthContext = Depends(require_permission("audit:read")),
    action: str | None = Query(default=None, max_length=100),
    outcome: str | None = Query(default=None, pattern="^(SUCCESS|FAILURE|DENIED)$"),
    actor: str | None = Query(default=None, max_length=320),
    resource_id: str | None = Query(default=None, max_length=100),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
):
    stmt = select(AuditLog)
    if action:
        stmt = stmt.where(AuditLog.action.ilike(f"{action}%"))
    if outcome:
        stmt = stmt.where(AuditLog.outcome == outcome)
    if actor:
        stmt = stmt.where(AuditLog.actor_email.ilike(f"%{actor.lower()}%"))
    if resource_id:
        stmt = stmt.where(AuditLog.resource_id == resource_id)
    if date_from:
        stmt = stmt.where(AuditLog.occurred_at >= date_from)
    if date_to:
        stmt = stmt.where(AuditLog.occurred_at <= date_to)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(AuditLog.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return Page(items=[AuditLogOut.model_validate(r) for r in rows], total=total, page=page, page_size=page_size)


@router.get("/audit-logs/export")
def export_audit_logs_csv(
    db: DB,
    _: AuthContext = Depends(require_permission("audit:read")),
    action: str | None = Query(default=None, max_length=100),
    outcome: str | None = Query(default=None, pattern="^(SUCCESS|FAILURE|DENIED)$"),
    actor: str | None = Query(default=None, max_length=320),
    resource_id: str | None = Query(default=None, max_length=100),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = Query(default=1000, ge=1, le=5000),
):
    import csv
    import io
    import json

    stmt = select(AuditLog)
    if action:
        stmt = stmt.where(AuditLog.action.ilike(f"{action}%"))
    if outcome:
        stmt = stmt.where(AuditLog.outcome == outcome)
    if actor:
        stmt = stmt.where(AuditLog.actor_email.ilike(f"%{actor.lower()}%"))
    if resource_id:
        stmt = stmt.where(AuditLog.resource_id == resource_id)
    if date_from:
        stmt = stmt.where(AuditLog.occurred_at >= date_from)
    if date_to:
        stmt = stmt.where(AuditLog.occurred_at <= date_to)

    rows = db.scalars(stmt.order_by(AuditLog.id.desc()).limit(limit)).all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "Timestamp (UTC)",
        "Action",
        "Outcome",
        "Actor Email",
        "Actor Role",
        "Resource Type",
        "Resource ID",
        "IP Address",
        "User Agent",
        "Request ID",
        "Details (JSON)",
    ])
    for r in rows:
        writer.writerow([
            r.occurred_at.isoformat() if r.occurred_at else "",
            r.action,
            r.outcome,
            r.actor_email or "",
            r.actor_role or "",
            r.resource_type or "",
            r.resource_id or "",
            r.ip_address or "",
            r.user_agent or "",
            r.request_id or "",
            json.dumps(r.details or {}),
        ])

    content = buf.getvalue().encode("utf-8-sig")  # BOM for Excel compatibility
    filename = f"policynest_audit_log_{utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        content=content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


def _storage_integration() -> IntegrationStatus:
    s = get_settings()
    try:
        st = get_storage().status()
        mode = "LOCAL_DEVELOPMENT" if st.mode == "LOCAL_DEVELOPMENT" else "LIVE"
        return IntegrationStatus(
            key="storage",
            name="Document storage",
            status="CONFIGURED" if st.configured else "NOT_CONFIGURED",
            mode=mode if st.configured else "NONE",
            detail=st.detail,
        )
    except Exception as exc:  # noqa: BLE001
        return IntegrationStatus(
            key="storage",
            name="Document storage",
            status="DEGRADED" if s.storage_provider == "s3" else "NOT_CONFIGURED",
            mode="NONE",
            detail=f"Storage backend unavailable: {type(exc).__name__}",
        )


def _email_integration() -> IntegrationStatus:
    s = get_settings()
    provider = get_provider()
    if not provider.configured:
        return IntegrationStatus(
            key="email",
            name="Email (SMTP)",
            status="NOT_CONFIGURED",
            mode="NONE",
            detail="Set SMTP_HOST and EMAIL_FROM. Verification and reset emails are not sent.",
        )
    local_hosts = {"localhost", "127.0.0.1", "mailpit"}
    mode = "LOCAL_DEVELOPMENT" if (s.smtp_host or "") in local_hosts else "LIVE"
    detail = (
        f"SMTP {s.smtp_host}:{s.smtp_port}. Local development mail catcher; messages are not delivered to real inboxes."
        if mode == "LOCAL_DEVELOPMENT"
        else f"SMTP {s.smtp_host}:{s.smtp_port}."
    )
    return IntegrationStatus(key="email", name="Email (SMTP)", status="CONFIGURED", mode=mode, detail=detail)


@router.get("/system/health", response_model=SystemHealthOut)
def system_health(db: DB, _: AuthContext = Depends(require_permission("system:read"))):
    s = get_settings()
    since = utcnow() - timedelta(hours=24)
    deliveries = dict(
        db.execute(
            select(EmailDelivery.status, func.count())
            .where(EmailDelivery.created_at >= since)
            .group_by(EmailDelivery.status)
        ).all()
    )
    integrations = (
        [_email_integration(), _storage_integration()]
        + [IntegrationStatus(**st) for st in get_verification_integration_statuses(db)]
        + [IntegrationStatus(**get_sms_integration_status(db)), IntegrationStatus(**get_webhook_integration_status(db))]
        + [
            IntegrationStatus(
                key=(lms_st := get_lms_integration_status(db))["key"],
                name=lms_st["name"],
                status=lms_st["status"],
                mode=lms_st["mode"],
                detail=lms_st["detail"],
            )
        ]
        + [
            IntegrationStatus(
                key=key,
                name=name,
                status="NOT_CONFIGURED",
                mode="NONE",
                detail=f"Adapter scheduled for {phase}. No verification is performed.",
            )
            for key, name, phase in PLANNED_INTEGRATIONS
        ]
    )
    database = database_status()
    healthy = database.get("connected") and database.get("migrations_current")
    return SystemHealthOut(
        status="healthy" if healthy else "degraded",
        app_env=s.app_env,
        version=s.app_version,
        database=database,
        integrations=integrations,
        email_deliveries_last_24h=deliveries,
    )


@router.get("/stats", response_model=AdminStatsOut)
def admin_stats(db: DB, _: AuthContext = Depends(require_permission("users:read", "audit:read"))):
    now = utcnow()
    by_role = dict(db.execute(select(Role.code, func.count(User.id)).outerjoin(User).group_by(Role.code)).all())

    def count(*where) -> int:
        return db.scalar(select(func.count()).select_from(User).where(*where)) or 0

    active_sessions = db.scalar(select(func.count()).select_from(UserSession).where(*live_session_filter(now))) or 0
    failed = (
        db.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(
                AuditLog.action == "auth.login",
                AuditLog.outcome == "FAILURE",
                AuditLog.occurred_at >= now - timedelta(hours=24),
            )
        )
        or 0
    )
    recent = db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(8)).all()
    return AdminStatsOut(
        users_by_role=by_role,
        active_users=count(User.is_active),
        inactive_users=count(User.is_active.is_(False)),
        unverified_users=count(User.email_verified_at.is_(None), User.password_hash.is_not(None)),
        pending_invitations=count(User.password_hash.is_(None)),
        active_sessions=active_sessions,
        registrations_last_7_days=count(User.created_at >= now - timedelta(days=7)),
        failed_logins_last_24h=failed,
        recent_audit=[AuditLogOut.model_validate(r) for r in recent],
    )
