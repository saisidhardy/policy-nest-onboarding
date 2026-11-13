"""Phase 5 reviewer operations portal: queue, claim/assign, fraud desk, review history, and analytics."""

import uuid

from fastapi import APIRouter, Depends, Query, Request

from app.api.deps import DB, AuthContext, enforce_policy, require_any_permission, require_permission
from app.rbac.policy import Resource
from app.schemas.application import ApplicationDetailOut
from app.schemas.review import (
    AssignableReviewerOut,
    FraudEscalationRequest,
    FraudResolutionRequest,
    ReviewAnalyticsOut,
    ReviewClaimRequest,
    ReviewHistoryPageOut,
    ReviewQueuePageOut,
    ReviewSlaStatusOut,
)
from app.services import applications as app_service
from app.services import review as review_service

router = APIRouter(prefix="/review", tags=["review"])


@router.get("/queue", response_model=ReviewQueuePageOut)
def get_review_queue(
    request: Request,
    db: DB,
    auth: AuthContext = Depends(require_permission("application:review")),
    q: str | None = Query(default=None, max_length=120),
    status: str | None = Query(default=None, max_length=120),
    region: str | None = Query(default=None, max_length=32),
    queue_view: str = Query(
        default="pending", pattern="^(all|pending|assigned_to_me|unassigned|escalated|fraud|open_appeals)$"
    ),
    outcome: str | None = Query(default=None, max_length=32),
    sort_by: str = Query(default="urgency", pattern="^(urgency|oldest_submitted|newest_submitted)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    enforce_policy(request, auth, "application:review", Resource(type="application_queue", region=auth.user.region))
    return review_service.get_review_queue(
        db,
        auth,
        q=q,
        status=status,
        region=region,
        queue_view=queue_view,
        outcome=outcome,
        sort_by=sort_by,
        page=page,
        page_size=page_size,
    )


@router.get("/reviewers", response_model=list[AssignableReviewerOut])
def get_assignable_reviewers(
    request: Request,
    db: DB,
    auth: AuthContext = Depends(require_permission("application:review")),
):
    enforce_policy(request, auth, "application:review", Resource(type="application_queue", region=auth.user.region))
    return review_service.list_assignable_reviewers(db, auth)


@router.post("/applications/{application_id}/claim", response_model=ApplicationDetailOut)
def claim_or_assign_application(
    application_id: uuid.UUID,
    body: ReviewClaimRequest,
    request: Request,
    db: DB,
    auth: AuthContext = Depends(require_permission("application:review")),
):
    app = app_service.get_application(db, application_id)
    enforce_policy(request, auth, "application:review", app_service.application_resource(app))
    updated = review_service.claim_or_assign_application(db, app, body, auth, request)
    return app_service.to_detail(updated)


@router.post("/applications/{application_id}/fraud-escalate", response_model=ApplicationDetailOut)
def escalate_application_fraud(
    application_id: uuid.UUID,
    body: FraudEscalationRequest,
    request: Request,
    db: DB,
    auth: AuthContext = Depends(require_any_permission("application:escalate", "fraud:review")),
):
    app = app_service.get_application(db, application_id)
    action = "fraud:review" if "fraud:review" in auth.permissions else "application:escalate"
    enforce_policy(request, auth, action, app_service.application_resource(app))
    updated = review_service.escalate_to_fraud_desk(db, app, body, auth, request)
    return app_service.to_detail(updated)


@router.post("/applications/{application_id}/fraud-resolve", response_model=ApplicationDetailOut)
def resolve_application_fraud(
    application_id: uuid.UUID,
    body: FraudResolutionRequest,
    request: Request,
    db: DB,
    auth: AuthContext = Depends(require_permission("fraud:review")),
):
    app = app_service.get_application(db, application_id)
    enforce_policy(request, auth, "fraud:review", app_service.application_resource(app))
    updated = review_service.resolve_fraud_escalation(db, app, body, auth, request)
    return app_service.to_detail(updated)


@router.get("/history", response_model=ReviewHistoryPageOut)
def list_review_history(
    request: Request,
    db: DB,
    auth: AuthContext = Depends(require_permission("application:review")),
    mine_only: bool = Query(default=False),
    decision: str | None = Query(default=None, max_length=32),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
):
    enforce_policy(request, auth, "application:review", Resource(type="application_queue", region=auth.user.region))
    return review_service.get_review_history(
        db, auth, mine_only=mine_only, decision=decision, page=page, page_size=page_size
    )


@router.get("/analytics", response_model=ReviewAnalyticsOut)
def get_operational_analytics(
    request: Request,
    db: DB,
    auth: AuthContext = Depends(require_permission("analytics:read")),
):
    enforce_policy(request, auth, "analytics:read", Resource(type="application_queue", region=auth.user.region))
    return review_service.get_review_analytics(db, auth)


@router.get("/sla-status", response_model=ReviewSlaStatusOut)
def get_reviewer_sla_status(
    request: Request,
    db: DB,
    auth: AuthContext = Depends(require_permission("application:review")),
    trigger_alert: bool = Query(default=False),
):
    enforce_policy(request, auth, "application:review", Resource(type="application_queue", region=auth.user.region))
    return review_service.check_review_sla_status(
        db,
        trigger_alert=trigger_alert,
        region_filter=auth.user.region,
    )
