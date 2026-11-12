"""External LMS integration adapter with strict provenance and honest unconfigured handling.

Supports three explicit modes configured via Settings.lms_provider:
- not_configured (default): returns explicit UNCONFIGURED state without fabricating learners or scores.
- http_api: invokes the configured external LMS REST API over HTTPS with Bearer auth and retries.
- sandbox (non-production only): deterministic simulation explicitly labelled is_simulated=True.
"""

import hashlib
import hmac
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.security import constant_time_equals
from app.models import Application
from app.models.base import utcnow
from app.models.training import TrainingRecord

# Statutory IRDAI 15.0-hour POSP training curriculum (IRDAI/INT/GDL/ECM/044/03/2017 §5)
IRDAI_POSP_MODULES: tuple[tuple[str, str, float], ...] = (
    ("MOD-1", "Fundamentals of Insurance & Uberrimae Fidei", 2.5),
    ("MOD-2", "Structure & Types of General and Life Insurance Contracts", 2.5),
    ("MOD-3", "Pre-underwritten POSP Product Features, Exclusions & Limits", 3.0),
    ("MOD-4", "Proposal Form Filling, Premium Calculation & Digital Issuance", 2.5),
    ("MOD-5", "Claims Reporting & Grievance Redressal Mechanisms", 2.5),
    ("MOD-6", "Prevention of Money Laundering Act (PMLA) & Anti-Fraud Standards", 2.0),
)


def initial_module_progress() -> list[dict[str, Any]]:
    return [
        {"code": code, "title": title, "required_hours": hours, "logged_hours": 0.0, "completed": False}
        for code, title, hours in IRDAI_POSP_MODULES
    ]


def distribute_module_hours(completed_hours: float) -> list[dict[str, Any]]:
    remaining = max(0.0, round(float(completed_hours), 2))
    out: list[dict[str, Any]] = []
    for code, title, req in IRDAI_POSP_MODULES:
        logged = round(min(req, remaining), 2)
        remaining = round(max(0.0, remaining - logged), 2)
        out.append(
            {
                "code": code,
                "title": title,
                "required_hours": req,
                "logged_hours": logged,
                "completed": logged >= req,
            }
        )
    return out


def get_lms_integration_status() -> dict[str, Any]:
    s = get_settings()
    webhook_ok = bool(s.lms_webhook_secret)
    if s.lms_provider == "not_configured":
        return {
            "key": "lms",
            "name": "LMS training & certification sync",
            "provider": s.lms_provider,
            "status": "NOT_CONFIGURED",
            "mode": "NONE",
            "webhook_configured": webhook_ok,
            "detail": (
                "External LMS URL and credentials are not configured. Set LMS_PROVIDER=http_api and LMS_API_BASE_URL "
                "(or LMS_PROVIDER=sandbox in non-production) to synchronize training progress and certificates."
            ),
        }
    if s.lms_provider == "sandbox":
        return {
            "key": "lms",
            "name": "LMS training & certification sync",
            "provider": s.lms_provider,
            "status": "CONFIGURED",
            "mode": "SANDBOX",
            "webhook_configured": webhook_ok,
            "detail": (
                "Non-production LMS sandbox adapter active (explicitly labelled is_simulated=true; "
                "blocked automatically in APP_ENV=production)."
            ),
        }
    if not s.lms_api_base_url:
        return {
            "key": "lms",
            "name": "LMS training & certification sync",
            "provider": s.lms_provider,
            "status": "DEGRADED",
            "mode": "NONE",
            "webhook_configured": webhook_ok,
            "detail": "LMS_PROVIDER=http_api is selected, but LMS_API_BASE_URL is missing.",
        }
    return {
        "key": "lms",
        "name": "LMS training & certification sync",
        "provider": s.lms_provider,
        "status": "CONFIGURED",
        "mode": "LIVE",
        "webhook_configured": webhook_ok,
        "detail": f"External LMS REST adapter configured against {s.lms_api_base_url.rstrip('/')} (course {s.lms_course_code}).",
    }


def verify_webhook_signature(raw_body: bytes, signature_header: str | None) -> tuple[bool, str]:
    s = get_settings()
    if not s.lms_webhook_secret:
        return False, "LMS_WEBHOOK_SECRET is not configured on this PolicyNest instance."
    if not signature_header:
        return False, "Missing X-LMS-Signature header."
    provided = signature_header.strip()
    if provided.startswith("sha256="):
        provided = provided[len("sha256=") :]
    expected = hmac.new(s.lms_webhook_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    if not constant_time_equals(provided.lower(), expected.lower()):
        return False, "Invalid LMS webhook HMAC signature."
    return True, "OK"


@dataclass
class LmsSyncResult:
    ok: bool
    provider_name: str
    origin: str  # REAL_LMS | SANDBOX | UNCONFIGURED
    is_simulated: bool
    http_status: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    retryable: bool = False

    external_enrollment_id: str | None = None
    lms_launch_url: str | None = None
    enrollment_status: str | None = None
    completed_hours: float | None = None
    module_progress: list[dict[str, Any]] | None = None
    exam_status: str | None = None
    exam_score_pct: float | None = None
    exam_attempts: int | None = None
    next_exam_eligible_at: datetime | None = None
    certification_status: str | None = None
    certificate_number: str | None = None
    certified_at: datetime | None = None
    request_payload: dict[str, Any] = field(default_factory=dict)
    response_payload: dict[str, Any] = field(default_factory=dict)


def _auth_headers() -> dict[str, str]:
    s = get_settings()
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if s.lms_api_key:
        headers["Authorization"] = f"Bearer {s.lms_api_key}"
    return headers


def enroll_applicant(app: Application, record: TrainingRecord) -> LmsSyncResult:
    s = get_settings()
    # Never send raw PAN, Aadhaar, or bank secrets to third-party LMS endpoints.
    req_payload = {
        "reference_code": app.reference_code,
        "candidate_name": app.full_name,
        "preferred_language": app.preferred_language,
        "region": app.region,
        "course_code": s.lms_course_code,
        "required_hours": float(s.lms_required_hours),
    }

    if s.lms_provider == "not_configured":
        return LmsSyncResult(
            ok=False,
            provider_name="external_lms",
            origin="UNCONFIGURED",
            is_simulated=False,
            error_code="LMS_NOT_CONFIGURED",
            error_message=(
                "External LMS provider is not configured. Configure LMS_PROVIDER=http_api and LMS_API_BASE_URL "
                "(or LMS_PROVIDER=sandbox in non-production) to enroll applicants."
            ),
            retryable=True,
            request_payload=req_payload,
        )

    if s.lms_provider == "sandbox":
        if s.app_env == "production":
            return LmsSyncResult(
                ok=False,
                provider_name="sandbox_lms",
                origin="UNCONFIGURED",
                is_simulated=False,
                error_code="SANDBOX_FORBIDDEN_IN_PROD",
                error_message="Sandbox LMS adapter is forbidden in production.",
                retryable=False,
                request_payload=req_payload,
            )
        ext_id = record.external_enrollment_id or f"SBX-{app.reference_code}"
        launch_url = f"{s.public_app_url.rstrip('/')}/app/training?enrollment={ext_id}"
        return LmsSyncResult(
            ok=True,
            provider_name="sandbox_lms",
            origin="SANDBOX",
            is_simulated=True,
            http_status=201,
            external_enrollment_id=ext_id,
            lms_launch_url=launch_url,
            enrollment_status="ENROLLED",
            completed_hours=0.0,
            module_progress=initial_module_progress(),
            exam_status="NOT_ELIGIBLE",
            certification_status="NOT_CERTIFIED",
            request_payload=req_payload,
            response_payload={
                "external_enrollment_id": ext_id,
                "enrollment_status": "ENROLLED",
                "is_simulated": True,
            },
        )

    # s.lms_provider == "http_api"
    if not s.lms_api_base_url:
        return LmsSyncResult(
            ok=False,
            provider_name="http_api",
            origin="UNCONFIGURED",
            is_simulated=False,
            error_code="LMS_MISSING_BASE_URL",
            error_message="LMS_PROVIDER=http_api requires LMS_API_BASE_URL to be configured.",
            retryable=True,
            request_payload=req_payload,
        )

    endpoint = f"{s.lms_api_base_url.rstrip('/')}/enrollments"
    try:
        resp = httpx.post(endpoint, json=req_payload, headers=_auth_headers(), timeout=float(s.lms_timeout_seconds))
    except httpx.TimeoutException:
        return LmsSyncResult(
            ok=False,
            provider_name="http_api",
            origin="REAL_LMS",
            is_simulated=False,
            error_code="LMS_TIMEOUT",
            error_message=f"LMS enrollment endpoint timed out after {s.lms_timeout_seconds}s.",
            retryable=True,
            request_payload=req_payload,
        )
    except httpx.RequestError as exc:
        return LmsSyncResult(
            ok=False,
            provider_name="http_api",
            origin="REAL_LMS",
            is_simulated=False,
            error_code="LMS_NETWORK_ERROR",
            error_message=f"Unable to reach LMS enrollment endpoint: {type(exc).__name__}.",
            retryable=True,
            request_payload=req_payload,
        )

    if resp.status_code >= 400:
        return LmsSyncResult(
            ok=False,
            provider_name="http_api",
            origin="REAL_LMS",
            is_simulated=False,
            http_status=resp.status_code,
            error_code=f"LMS_HTTP_{resp.status_code}",
            error_message=f"External LMS returned HTTP {resp.status_code} during enrollment.",
            retryable=resp.status_code >= 500 or resp.status_code == 429,
            request_payload=req_payload,
            response_payload={"status_code": resp.status_code},
        )

    try:
        data = resp.json()
    except ValueError:
        return LmsSyncResult(
            ok=False,
            provider_name="http_api",
            origin="REAL_LMS",
            is_simulated=False,
            http_status=resp.status_code,
            error_code="LMS_INVALID_RESPONSE",
            error_message="External LMS returned invalid JSON on enrollment.",
            retryable=True,
            request_payload=req_payload,
        )

    ext_id = data.get("external_enrollment_id") or data.get("enrollment_id")
    if not ext_id:
        return LmsSyncResult(
            ok=False,
            provider_name="http_api",
            origin="REAL_LMS",
            is_simulated=False,
            http_status=resp.status_code,
            error_code="LMS_INVALID_RESPONSE",
            error_message="External LMS enrollment response missing external_enrollment_id.",
            retryable=False,
            request_payload=req_payload,
            response_payload=data if isinstance(data, dict) else {},
        )

    return LmsSyncResult(
        ok=True,
        provider_name="http_api",
        origin="REAL_LMS",
        is_simulated=False,
        http_status=resp.status_code,
        external_enrollment_id=str(ext_id),
        lms_launch_url=data.get("launch_url") or data.get("lms_launch_url"),
        enrollment_status=data.get("enrollment_status") or "ENROLLED",
        completed_hours=float(data.get("completed_hours") or 0.0),
        module_progress=data.get("module_progress") or initial_module_progress(),
        exam_status=data.get("exam_status") or "NOT_ELIGIBLE",
        certification_status=data.get("certification_status") or "NOT_CERTIFIED",
        request_payload=req_payload,
        response_payload=data,
    )


def fetch_training_status(
    app: Application,
    record: TrainingRecord,
    *,
    sandbox_action: str | None = None,
) -> LmsSyncResult:
    s = get_settings()
    req_payload = {
        "reference_code": app.reference_code,
        "external_enrollment_id": record.external_enrollment_id,
    }

    if s.lms_provider == "not_configured":
        return LmsSyncResult(
            ok=False,
            provider_name="external_lms",
            origin="UNCONFIGURED",
            is_simulated=False,
            error_code="LMS_NOT_CONFIGURED",
            error_message=(
                "External LMS provider is not configured. Progress cannot be polled until LMS_PROVIDER is set."
            ),
            retryable=True,
            request_payload=req_payload,
        )

    if s.lms_provider == "sandbox":
        if s.app_env == "production":
            return LmsSyncResult(
                ok=False,
                provider_name="sandbox_lms",
                origin="UNCONFIGURED",
                is_simulated=False,
                error_code="SANDBOX_FORBIDDEN_IN_PROD",
                error_message="Sandbox LMS adapter is forbidden in production.",
                retryable=False,
                request_payload=req_payload,
            )
        if sandbox_action == "SIMULATE_SYNC_ERROR":
            return LmsSyncResult(
                ok=False,
                provider_name="sandbox_lms",
                origin="SANDBOX",
                is_simulated=True,
                http_status=503,
                error_code="LMS_TEMPORARY_UNAVAILABLE",
                error_message="Sandbox LMS simulated transient HTTP 503 synchronization failure for retry testing.",
                retryable=True,
                request_payload={**req_payload, "sandbox_action": sandbox_action},
            )

        now = utcnow()
        current_hours = float(record.completed_hours or 0.0)
        req_hours = float(record.required_hours or s.lms_required_hours)
        enrollment_status = record.enrollment_status
        exam_status = record.exam_status
        exam_score = float(record.exam_score_pct) if record.exam_score_pct is not None else None
        exam_attempts = record.exam_attempts
        next_exam_eligible = record.next_exam_eligible_at
        cert_status = record.certification_status
        cert_number = record.certificate_number
        certified_at = record.certified_at

        if sandbox_action == "ADVANCE_7_5H":
            current_hours = max(current_hours, round(req_hours / 2.0, 2))
            enrollment_status = "IN_PROGRESS"
        elif sandbox_action == "COMPLETE_15H":
            current_hours = req_hours
            enrollment_status = "COMPLETED"
            if exam_status in ("NOT_ELIGIBLE", "FAILED"):
                exam_status = "ELIGIBLE"
        elif sandbox_action == "FAIL_EXAM":
            current_hours = req_hours
            enrollment_status = "COMPLETED"
            exam_attempts = record.exam_attempts + 1
            exam_score = 42.0
            exam_status = "COOLDOWN"
            next_exam_eligible = now + timedelta(hours=s.lms_exam_cooldown_hours)
        elif sandbox_action == "PASS_EXAM":
            current_hours = req_hours
            enrollment_status = "COMPLETED"
            exam_attempts = record.exam_attempts + 1
            exam_score = 84.0
            exam_status = "PASSED"
            next_exam_eligible = None
            cert_status = "CERTIFIED"
            cert_number = cert_number or f"SBX-CERT-{app.reference_code}"
            certified_at = certified_at or now
        elif current_hours >= req_hours and enrollment_status != "COMPLETED":
            enrollment_status = "COMPLETED"

        return LmsSyncResult(
            ok=True,
            provider_name="sandbox_lms",
            origin="SANDBOX",
            is_simulated=True,
            http_status=200,
            external_enrollment_id=record.external_enrollment_id or f"SBX-{app.reference_code}",
            lms_launch_url=record.lms_launch_url
            or f"{s.public_app_url.rstrip('/')}/app/training?enrollment=SBX-{app.reference_code}",
            enrollment_status=enrollment_status,
            completed_hours=current_hours,
            module_progress=distribute_module_hours(current_hours),
            exam_status=exam_status,
            exam_score_pct=exam_score,
            exam_attempts=exam_attempts,
            next_exam_eligible_at=next_exam_eligible,
            certification_status=cert_status,
            certificate_number=cert_number,
            certified_at=certified_at,
            request_payload={**req_payload, "sandbox_action": sandbox_action},
            response_payload={
                "enrollment_status": enrollment_status,
                "completed_hours": current_hours,
                "exam_status": exam_status,
                "certification_status": cert_status,
                "is_simulated": True,
            },
        )

    # s.lms_provider == "http_api"
    if not s.lms_api_base_url:
        return LmsSyncResult(
            ok=False,
            provider_name="http_api",
            origin="UNCONFIGURED",
            is_simulated=False,
            error_code="LMS_MISSING_BASE_URL",
            error_message="LMS_PROVIDER=http_api requires LMS_API_BASE_URL to be configured.",
            retryable=True,
            request_payload=req_payload,
        )
    if not record.external_enrollment_id:
        return enroll_applicant(app, record)

    endpoint = f"{s.lms_api_base_url.rstrip('/')}/enrollments/{record.external_enrollment_id}/status"
    try:
        resp = httpx.get(endpoint, headers=_auth_headers(), timeout=float(s.lms_timeout_seconds))
    except httpx.TimeoutException:
        return LmsSyncResult(
            ok=False,
            provider_name="http_api",
            origin="REAL_LMS",
            is_simulated=False,
            error_code="LMS_TIMEOUT",
            error_message=f"LMS status endpoint timed out after {s.lms_timeout_seconds}s.",
            retryable=True,
            request_payload=req_payload,
        )
    except httpx.RequestError as exc:
        return LmsSyncResult(
            ok=False,
            provider_name="http_api",
            origin="REAL_LMS",
            is_simulated=False,
            error_code="LMS_NETWORK_ERROR",
            error_message=f"Unable to reach LMS status endpoint: {type(exc).__name__}.",
            retryable=True,
            request_payload=req_payload,
        )

    if resp.status_code >= 400:
        return LmsSyncResult(
            ok=False,
            provider_name="http_api",
            origin="REAL_LMS",
            is_simulated=False,
            http_status=resp.status_code,
            error_code=f"LMS_HTTP_{resp.status_code}",
            error_message=f"External LMS status check returned HTTP {resp.status_code}.",
            retryable=resp.status_code >= 500 or resp.status_code == 429,
            request_payload=req_payload,
        )

    try:
        data = resp.json()
    except ValueError:
        return LmsSyncResult(
            ok=False,
            provider_name="http_api",
            origin="REAL_LMS",
            is_simulated=False,
            http_status=resp.status_code,
            error_code="LMS_INVALID_RESPONSE",
            error_message="External LMS returned invalid JSON on status check.",
            retryable=True,
            request_payload=req_payload,
        )

    return LmsSyncResult(
        ok=True,
        provider_name="http_api",
        origin="REAL_LMS",
        is_simulated=False,
        http_status=resp.status_code,
        external_enrollment_id=record.external_enrollment_id,
        lms_launch_url=data.get("launch_url") or data.get("lms_launch_url") or record.lms_launch_url,
        enrollment_status=data.get("enrollment_status"),
        completed_hours=float(data["completed_hours"]) if data.get("completed_hours") is not None else None,
        module_progress=data.get("module_progress"),
        exam_status=data.get("exam_status"),
        exam_score_pct=float(data["exam_score_pct"]) if data.get("exam_score_pct") is not None else None,
        exam_attempts=data.get("exam_attempts"),
        certification_status=data.get("certification_status"),
        certificate_number=data.get("certificate_number"),
        request_payload=req_payload,
        response_payload=data if isinstance(data, dict) else {},
    )
