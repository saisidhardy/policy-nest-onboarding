"""Tests for product journey tracking, SLA turnaround, cost intelligence, and observability."""

import uuid
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.analytics import (
    ApiCostRecord,
    ProductEvent,
    ProviderPricingRegistry,
    WorkflowStageTiming,
)
from app.schemas.analytics import ProductEventCreate
from app.services import analytics as analytics_service


def test_sanitize_properties_masks_aadhaar():
    """Ensure DPDP Act compliance: 12-digit Aadhaar numbers are masked in properties."""
    raw_props = {
        "candidate_aadhaar": "998877665544",
        "nested": {"aadhaar_ref": "123456789012"},
        "clean_field": "Rajiv Sharma",
    }
    clean = analytics_service.sanitize_properties(raw_props)
    assert "998877665544" not in clean["candidate_aadhaar"]
    assert clean["candidate_aadhaar"] == "XXXX-XXXX-XXXX"
    assert clean["nested"]["aadhaar_ref"] == "XXXX-XXXX-XXXX"
    assert clean["clean_field"] == "Rajiv Sharma"


def test_record_and_reconstruct_applicant_journey(db_session: Session):
    """AC 1 & 4: Reconstruct applicant journey distinguishing active vs waiting vs elapsed time."""
    app_id = uuid.uuid4()
    anon_id = "anon_test_user_42"
    sess_id = "sess_test_101"

    # Step 1: Registration
    analytics_service.record_product_event(
        db_session,
        ProductEventCreate(
            event_name="registration.completed",
            anonymous_id=anon_id,
            session_id=sess_id,
            application_id=app_id,
            stage="REGISTRATION",
            active_time_ms=12000,
            waiting_time_ms=2000,
            stage_duration_ms=14000,
        ),
    )

    # Step 2: Upload Documents
    analytics_service.record_product_event(
        db_session,
        ProductEventCreate(
            event_name="document.upload_completed",
            anonymous_id=anon_id,
            session_id=sess_id,
            application_id=app_id,
            stage="DOCUMENTS",
            active_time_ms=45000,
            waiting_time_ms=5000,
            stage_duration_ms=50000,
        ),
    )

    # Reconstruct
    journey = analytics_service.reconstruct_applicant_journey(db_session, app_id)
    assert journey.total_events_count == 2
    assert journey.active_time_hours > 0
    assert len(journey.events) == 2
    assert journey.events[0].event_name == "registration.completed"
    assert journey.events[1].event_name == "document.upload_completed"


def test_funnel_and_conversion_calculation(db_session: Session):
    """AC 2: Funnel conversion and abandonment rates are calculated from actual events."""
    funnel = analytics_service.get_funnel_analytics(db_session)
    assert len(funnel.funnel_stages) == 9
    assert funnel.total_visitors >= 1
    assert funnel.overall_completion_rate_pct >= 0.0
    for stage in funnel.funnel_stages:
        assert stage.count >= 0
        assert 0.0 <= stage.conversion_from_top_pct <= 100.0


def test_turnaround_and_sla_5_7_days(db_session: Session):
    """AC 3: Stage-wise turnaround times and 5.7d SLA targets calculated."""
    sla_data = analytics_service.get_turnaround_sla_analytics(db_session)
    assert sla_data.baseline_median_days == 8.4
    assert sla_data.target_operational_days == 5.7
    assert sla_data.p50_turnaround_days > 0
    assert "Document Pre-Capture & Ingestion" in sla_data.stage_duration_breakdown_hours
    assert "active_applicant_time_hours" in sla_data.active_vs_waiting_hours


def test_api_and_ai_cost_attribution(db_session: Session):
    """AC 5 & 6: Cost per application, provider attribution, and token tracking."""
    app_id = uuid.uuid4()

    # Record Gemini call
    analytics_service.record_api_cost(
        db_session,
        provider="GEMINI",
        service="GEMINI_VISION_OCR",
        operation="DOCUMENT_EXTRACTION",
        application_id=app_id,
        model_name="gemini-1.5-flash",
        input_tokens=2000,
        output_tokens=500,
        units_processed=1,
        latency_ms=750,
    )

    costs = analytics_service.get_cost_intelligence_analytics(db_session)
    assert costs.total_api_expenditure_inr > 0
    assert "GEMINI" in costs.cost_by_provider
    assert costs.avg_cost_per_application_inr >= 0.0


def test_executive_and_observability_dashboards(db_session: Session):
    """AC 7 & 8: Executive metrics and technical observability dashboards."""
    obs = analytics_service.get_technical_observability_analytics(db_session)
    assert obs.api_latency_p50_ms > 0
    assert obs.db_pool_status["status"] == "HEALTHY"

    exec_metrics = analytics_service.get_executive_business_analytics(db_session)
    assert exec_metrics.cycle_time_reduction_pct > 0
    assert exec_metrics.traditional_paper_cost_per_agent_inr == 1450.00
    assert exec_metrics.regulatory_leakage_rate_pct == 0.0
