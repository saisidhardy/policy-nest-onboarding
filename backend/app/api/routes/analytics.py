"""Analytics routes for applicant journey tracking, SLA turnaround, cost intelligence, and observability."""

import uuid

from fastapi import APIRouter, Depends, Request

from app.api.deps import DB, AuthContext, enforce_policy, get_current_user_optional, require_any_permission, require_permission
from app.rbac.policy import Resource
from app.schemas.analytics import (
    ApplicantJourneyOut,
    CostDashboardOut,
    ExecutiveDashboardOut,
    FunnelDashboardOut,
    ObservabilityDashboardOut,
    ProductEventCreate,
    ProductEventOut,
    TurnaroundDashboardOut,
)
from app.services import analytics as analytics_service

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.post("/events", response_model=ProductEventOut, summary="Ingest client-side product event")
def ingest_product_event(
    event: ProductEventCreate,
    db: DB,
    auth: AuthContext | None = Depends(get_current_user_optional),
) -> ProductEventOut:
    """Record a client lifecycle event with DPDP compliance and zero raw PII."""
    user_id = auth.user.id if auth else None
    pe = analytics_service.record_product_event(db, event, user_id=user_id)
    return ProductEventOut.model_validate(pe)


@router.get("/dashboards/funnel", response_model=FunnelDashboardOut, summary="Applicant Funnel & Conversion Dashboard")
def get_funnel_dashboard(
    request: Request,
    db: DB,
    auth: AuthContext = Depends(require_permission("analytics:read")),
) -> FunnelDashboardOut:
    """Aggregate actual persisted events into configurable conversion and drop-off funnels."""
    enforce_policy(request, auth, "analytics:read", Resource(type="analytics", region=auth.user.region))
    return analytics_service.get_funnel_analytics(db)


@router.get("/dashboards/turnaround", response_model=TurnaroundDashboardOut, summary="Turnaround & 5.7d SLA Dashboard")
def get_turnaround_dashboard(
    request: Request,
    db: DB,
    auth: AuthContext = Depends(require_permission("analytics:read")),
) -> TurnaroundDashboardOut:
    """Track P50/P90/P95 turnaround times, active vs waiting time, and 5.7-day SLA performance."""
    enforce_policy(request, auth, "analytics:read", Resource(type="analytics", region=auth.user.region))
    return analytics_service.get_turnaround_sla_analytics(db)


@router.get("/dashboards/cost", response_model=CostDashboardOut, summary="API, LLM, and Infrastructure Cost Dashboard")
def get_cost_dashboard(
    request: Request,
    db: DB,
    auth: AuthContext = Depends(require_permission("analytics:read")),
) -> CostDashboardOut:
    """Break down API, LLM token, and OCR expenditures per application and provider."""
    enforce_policy(request, auth, "analytics:read", Resource(type="analytics", region=auth.user.region))
    return analytics_service.get_cost_intelligence_analytics(db)


@router.get("/dashboards/observability", response_model=ObservabilityDashboardOut, summary="System Observability & Latency Dashboard")
def get_observability_dashboard(
    request: Request,
    db: DB,
    auth: AuthContext = Depends(require_any_permission("analytics:read", "system:read")),
) -> ObservabilityDashboardOut:
    """Monitor API latencies, error distributions, database connection pool, and integration node health."""
    enforce_policy(request, auth, "system:read" if "system:read" in auth.permissions else "analytics:read", Resource(type="system", region=auth.user.region))
    return analytics_service.get_technical_observability_analytics(db)


@router.get("/dashboards/executive", response_model=ExecutiveDashboardOut, summary="Executive Business Performance Dashboard")
def get_executive_dashboard(
    request: Request,
    db: DB,
    auth: AuthContext = Depends(require_permission("analytics:read")),
) -> ExecutiveDashboardOut:
    """High-level unit economics, completion rates, and net cost savings vs manual paper process."""
    enforce_policy(request, auth, "analytics:read", Resource(type="analytics", region=auth.user.region))
    return analytics_service.get_executive_business_analytics(db)


@router.get("/journey/{application_id}", response_model=ApplicantJourneyOut, summary="Reconstruct applicant journey")
def get_applicant_journey(
    application_id: uuid.UUID,
    request: Request,
    db: DB,
    auth: AuthContext = Depends(require_any_permission("application:read_own", "application:read_any", "analytics:read")),
) -> ApplicantJourneyOut:
    """Reconstruct an applicant's complete journey timeline from persisted lifecycle events."""
    return analytics_service.reconstruct_applicant_journey(db, application_id)
