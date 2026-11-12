"""Phase 6 Training & LMS synchronization API routes."""

import uuid

from fastapi import APIRouter, Depends, Query, Request

from app.api.deps import DB, AuthContext, enforce_policy, require_any_permission
from app.core.errors import AppError
from app.rbac.policy import Resource
from app.schemas.training import (
    BatchRetryOut,
    LmsWebhookPayload,
    TrainingOverviewOut,
    TrainingRecordOut,
    TrainingSyncRequest,
)
from app.services import applications as app_service
from app.services import lms_adapter
from app.services import training as training_service

router = APIRouter(tags=["training"])


@router.get("/applications/{application_id}/training", response_model=TrainingRecordOut)
def get_application_training(
    application_id: uuid.UUID,
    request: Request,
    db: DB,
    auth: AuthContext = Depends(require_any_permission("application:read_own", "application:read_any")),
):
    app = app_service.get_application(db, application_id)
    enforce_policy(request, auth, app_service.resolve_read_permission(auth), app_service.application_resource(app))
    record = training_service.get_or_create_training_record(db, app)
    db.commit()
    db.refresh(record)
    return training_service.to_training_out(db, app, record)


@router.post("/applications/{application_id}/training/enroll", response_model=TrainingRecordOut)
def enroll_application_training(
    application_id: uuid.UUID,
    request: Request,
    db: DB,
    auth: AuthContext = Depends(require_any_permission("application:read_own", "application:review")),
):
    app = app_service.get_application(db, application_id)
    perm = (
        "application:read_own"
        if "application:read_own" in auth.permissions and app.user_id == auth.user.id
        else "application:review"
    )
    enforce_policy(request, auth, perm, app_service.application_resource(app))
    return training_service.enroll_in_training(db, app, auth, request)


@router.post("/applications/{application_id}/training/sync", response_model=TrainingRecordOut)
def sync_application_training(
    application_id: uuid.UUID,
    body: TrainingSyncRequest,
    request: Request,
    db: DB,
    auth: AuthContext = Depends(require_any_permission("application:read_own", "application:review")),
):
    app = app_service.get_application(db, application_id)
    perm = (
        "application:read_own"
        if "application:read_own" in auth.permissions and app.user_id == auth.user.id
        else "application:review"
    )
    enforce_policy(request, auth, perm, app_service.application_resource(app))
    return training_service.sync_training_status(
        db,
        app,
        auth,
        request,
        sandbox_action=body.sandbox_action,
        is_retry=False,
    )


@router.post("/applications/{application_id}/training/retry", response_model=TrainingRecordOut)
def retry_application_training_sync(
    application_id: uuid.UUID,
    request: Request,
    db: DB,
    auth: AuthContext = Depends(require_any_permission("application:read_own", "application:review")),
):
    app = app_service.get_application(db, application_id)
    perm = (
        "application:read_own"
        if "application:read_own" in auth.permissions and app.user_id == auth.user.id
        else "application:review"
    )
    enforce_policy(request, auth, perm, app_service.application_resource(app))
    return training_service.sync_training_status(db, app, auth, request, is_retry=True)


@router.get("/training/overview", response_model=TrainingOverviewOut)
def get_training_overview(
    request: Request,
    db: DB,
    auth: AuthContext = Depends(require_any_permission("application:review", "system:read")),
    q: str | None = Query(default=None, max_length=120),
    sync_status: str | None = Query(default=None, max_length=32),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    perm = "application:review" if "application:review" in auth.permissions else "system:read"
    enforce_policy(request, auth, perm, Resource(type="training_queue", region=auth.user.region))
    return training_service.list_training_overview(
        db, auth, q=q, sync_status=sync_status, page=page, page_size=page_size
    )


@router.post("/training/retry-due", response_model=BatchRetryOut)
def retry_due_training_syncs(
    request: Request,
    db: DB,
    auth: AuthContext = Depends(require_any_permission("application:review", "system:read")),
):
    perm = "application:review" if "application:review" in auth.permissions else "system:read"
    enforce_policy(request, auth, perm, Resource(type="training_queue", region=auth.user.region))
    return training_service.retry_pending_syncs(db, auth, request)


@router.post("/training/webhooks/lms", response_model=TrainingRecordOut)
async def receive_lms_webhook(request: Request, db: DB):
    raw_body = await request.body()
    ok, reason = lms_adapter.verify_webhook_signature(raw_body, request.headers.get("x-lms-signature"))
    if not ok:
        raise AppError(401, "INVALID_WEBHOOK_SIGNATURE", reason)
    payload = LmsWebhookPayload.model_validate_json(raw_body)
    return training_service.process_inbound_webhook(db, payload, request)
