"""Phase 4 rules configuration, deterministic evaluation, reviewer decisions, appeals, and reapplications."""

import uuid

from fastapi import APIRouter, Depends, Request

from app.api.deps import DB, AuthContext, enforce_policy, require_any_permission, require_permission
from app.rbac.policy import Resource
from app.schemas.application import ApplicationDetailOut
from app.schemas.rules import (
    AppealCreateRequest,
    AppealResolveRequest,
    ApplicationAppealOut,
    ApplicationDecisionOut,
    ApplicationDecisionSummaryOut,
    EvaluateApplicationRequest,
    ReapplyRequest,
    ReviewerDecisionRequest,
    RuleExecutionOut,
    RuleSetCreateRequest,
    RuleSetOut,
)
from app.services import applications as app_service
from app.services import rules_engine

router = APIRouter(tags=["rules"])


@router.get("/rulesets", response_model=list[RuleSetOut])
def list_rule_sets(
    request: Request,
    db: DB,
    auth: AuthContext = Depends(require_any_permission("config:manage", "application:review", "application:decide")),
):
    action = "config:manage" if "config:manage" in auth.permissions else "application:review"
    enforce_policy(request, auth, action, Resource(type="rule_set"))
    return rules_engine.list_rulesets(db)


@router.post("/rulesets", response_model=RuleSetOut, status_code=201)
def create_rule_set(
    body: RuleSetCreateRequest,
    request: Request,
    db: DB,
    auth: AuthContext = Depends(require_permission("config:manage")),
):
    enforce_policy(request, auth, "config:manage", Resource(type="rule_set"))
    return rules_engine.create_ruleset_version(db, body, auth, request)


@router.post("/rulesets/{ruleset_id}/activate", response_model=RuleSetOut)
def activate_rule_set(
    ruleset_id: uuid.UUID,
    request: Request,
    db: DB,
    auth: AuthContext = Depends(require_permission("config:manage")),
):
    enforce_policy(request, auth, "config:manage", Resource(type="rule_set"))
    return rules_engine.activate_ruleset_version(db, ruleset_id, auth, request)


@router.get("/applications/{application_id}/decisions", response_model=ApplicationDecisionSummaryOut)
def get_application_decisions(
    application_id: uuid.UUID,
    request: Request,
    db: DB,
    auth: AuthContext = Depends(require_any_permission("application:read_own", "application:read_any")),
):
    app = app_service.get_application(db, application_id)
    enforce_policy(
        request,
        auth,
        app_service.resolve_read_permission(auth),
        app_service.application_resource(app),
    )
    return rules_engine.get_decision_summary(db, app)


@router.post("/applications/{application_id}/evaluate", response_model=RuleExecutionOut)
def evaluate_application_rules(
    application_id: uuid.UUID,
    request: Request,
    db: DB,
    body: EvaluateApplicationRequest | None = None,
    auth: AuthContext = Depends(
        require_any_permission("application:create", "application:review", "application:decide")
    ),
):
    app = app_service.get_application(db, application_id)
    action = (
        "application:review"
        if "application:review" in auth.permissions
        else ("application:decide" if "application:decide" in auth.permissions else "application:create")
    )
    enforce_policy(request, auth, action, app_service.application_resource(app))
    req_body = body or EvaluateApplicationRequest()
    return rules_engine.evaluate_application(
        db,
        app,
        auth,
        request,
        trigger_source=req_body.trigger_source,
        apply_transition=req_body.apply_transition,
    )


@router.post("/applications/{application_id}/decide", response_model=ApplicationDecisionOut)
def decide_application(
    application_id: uuid.UUID,
    body: ReviewerDecisionRequest,
    request: Request,
    db: DB,
    auth: AuthContext = Depends(
        require_any_permission("application:decide", "application:decide_escalated", "application:escalate")
    ),
):
    app = app_service.get_application(db, application_id)
    action = (
        "application:escalate"
        if body.decision == "ESCALATE" and "application:escalate" in auth.permissions
        else (
            "application:decide_escalated"
            if "application:decide_escalated" in auth.permissions
            else "application:decide"
        )
    )
    enforce_policy(request, auth, action, app_service.application_resource(app))
    return rules_engine.record_reviewer_decision(db, app, body, auth, request)


@router.post("/applications/{application_id}/reapply", response_model=ApplicationDetailOut, status_code=201)
def reapply_application(
    application_id: uuid.UUID,
    body: ReapplyRequest,
    request: Request,
    db: DB,
    auth: AuthContext = Depends(require_permission("application:create")),
):
    parent_app = app_service.get_application(db, application_id)
    enforce_policy(request, auth, "application:create", app_service.application_resource(parent_app))
    child = rules_engine.reapply_after_rejection(db, parent_app, body, auth, request)
    return app_service.to_detail(child)


@router.post("/applications/{application_id}/appeal", response_model=ApplicationAppealOut, status_code=201)
def submit_application_appeal(
    application_id: uuid.UUID,
    body: AppealCreateRequest,
    request: Request,
    db: DB,
    auth: AuthContext = Depends(require_permission("application:create")),
):
    app = app_service.get_application(db, application_id)
    enforce_policy(request, auth, "application:create", app_service.application_resource(app))
    return rules_engine.submit_appeal(db, app, body, auth, request)


@router.post("/applications/{application_id}/appeals/{appeal_id}/resolve", response_model=ApplicationAppealOut)
def resolve_application_appeal(
    application_id: uuid.UUID,
    appeal_id: uuid.UUID,
    body: AppealResolveRequest,
    request: Request,
    db: DB,
    auth: AuthContext = Depends(require_permission("application:decide_escalated")),
):
    app = app_service.get_application(db, application_id)
    enforce_policy(request, auth, "application:decide_escalated", app_service.application_resource(app))
    return rules_engine.resolve_appeal(db, app, appeal_id, body, auth, request)
