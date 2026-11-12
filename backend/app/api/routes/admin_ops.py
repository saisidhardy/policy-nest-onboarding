"""Phase 7 Administrator Operations API routes (dashboard, reviewers, applications, role permissions, config)."""

import uuid

from fastapi import APIRouter, Depends, Query, Request

from app.api.deps import DB, AuthContext, require_permission
from app.schemas.admin import (
    AdminApplicationItemOut,
    AdminApplicationPageOut,
    AdminAssignReviewerRequest,
    AdminConfigBundleOut,
    AdminDashboardOut,
    IntegrationProbeOut,
    IntegrationsConfigOut,
    IntegrationsMonitorOut,
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
from app.services import admin_ops

router = APIRouter(prefix="/admin", tags=["admin-operations"])


@router.get("/dashboard", response_model=AdminDashboardOut)
def get_dashboard(db: DB, _: AuthContext = Depends(require_permission("users:read", "audit:read"))):
    return admin_ops.get_admin_dashboard(db)


@router.get("/reviewers", response_model=list[ReviewerWorkloadOut])
def list_reviewers(
    db: DB,
    _: AuthContext = Depends(require_permission("users:read")),
    region: str | None = Query(default=None, max_length=32),
    role: str | None = Query(default=None, pattern="^(REVIEWER|SENIOR_REVIEWER)$"),
):
    return admin_ops.list_reviewers_workload(db, region=region, role_filter=role)


@router.post("/reviewers/{user_id}/reassign-workload", response_model=ReassignWorkloadOut)
def reassign_workload(
    user_id: uuid.UUID,
    body: ReassignWorkloadRequest,
    request: Request,
    db: DB,
    ctx: AuthContext = Depends(require_permission("users:manage")),
):
    return admin_ops.reassign_reviewer_workload(db, request, source_user_id=user_id, body=body, actor=ctx.user)


@router.get("/applications", response_model=AdminApplicationPageOut)
def list_admin_applications(
    db: DB,
    _: AuthContext = Depends(require_permission("application:read_any")),
    q: str | None = Query(default=None, max_length=200),
    status: str | None = Query(default=None, max_length=32),
    region: str | None = Query(default=None, max_length=32),
    escalated_only: bool = False,
    unassigned_only: bool = False,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
):
    return admin_ops.list_admin_applications(
        db,
        q=q,
        status_filter=status,
        region=region,
        escalated_only=escalated_only,
        unassigned_only=unassigned_only,
        page=page,
        page_size=page_size,
    )


@router.post("/applications/{application_id}/assign", response_model=AdminApplicationItemOut)
def assign_reviewer(
    application_id: uuid.UUID,
    body: AdminAssignReviewerRequest,
    request: Request,
    db: DB,
    ctx: AuthContext = Depends(require_permission("users:manage")),
):
    return admin_ops.assign_application_reviewer(db, request, application_id=application_id, body=body, actor=ctx.user)


@router.put("/roles/{role_code}/permissions", response_model=RoleDetailOut)
def update_role_permissions(
    role_code: str,
    body: UpdateRolePermissionsRequest,
    request: Request,
    db: DB,
    ctx: AuthContext = Depends(require_permission("roles:read", "config:manage")),
):
    return admin_ops.update_role_permissions(db, request, role_code=role_code, body=body, actor=ctx.user)


@router.get("/config", response_model=AdminConfigBundleOut)
def get_config(db: DB, _: AuthContext = Depends(require_permission("system:read", "config:manage"))):
    return admin_ops.get_config_bundle(db)


@router.put("/config/lms", response_model=LmsConfigOut)
def update_lms_config(
    body: UpdateLmsConfigRequest,
    request: Request,
    db: DB,
    ctx: AuthContext = Depends(require_permission("config:manage")),
):
    return admin_ops.update_lms_config(db, request, body, ctx.user)


@router.put("/config/integrations", response_model=IntegrationsConfigOut)
def update_integrations_config(
    body: UpdateIntegrationsConfigRequest,
    request: Request,
    db: DB,
    ctx: AuthContext = Depends(require_permission("config:manage")),
):
    return admin_ops.update_integrations_config(db, request, body, ctx.user)


@router.put("/config/platform", response_model=PlatformConfigOut)
def update_platform_config(
    body: UpdatePlatformConfigRequest,
    request: Request,
    db: DB,
    ctx: AuthContext = Depends(require_permission("config:manage")),
):
    return admin_ops.update_platform_config(db, request, body, ctx.user)


@router.post("/config/reset/{section}", response_model=AdminConfigBundleOut)
def reset_config_section(
    section: str,
    request: Request,
    db: DB,
    ctx: AuthContext = Depends(require_permission("config:manage")),
):
    return admin_ops.reset_config_section(db, request, section=section, actor=ctx.user)


@router.post("/integrations/probe", response_model=list[IntegrationProbeOut])
def probe_integrations(
    request: Request,
    db: DB,
    key: str | None = Query(default=None, max_length=64),
    ctx: AuthContext = Depends(require_permission("config:manage")),
):
    return admin_ops.probe_integrations_action(db, request, actor=ctx.user, target_key=key)


@router.get("/integrations/monitor", response_model=IntegrationsMonitorOut)
def get_integrations_monitor(
    db: DB,
    _: AuthContext = Depends(require_permission("system:read")),
):
    return admin_ops.get_integrations_monitor_action(db)


@router.post("/integrations/sms/retry-failed", response_model=SmsRetryOut)
def retry_failed_sms(
    request: Request,
    db: DB,
    ctx: AuthContext = Depends(require_permission("config:manage")),
):
    return admin_ops.retry_failed_sms_action(db, request, actor=ctx.user)
