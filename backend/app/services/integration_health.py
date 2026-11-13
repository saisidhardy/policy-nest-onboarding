"""Phase 8 active integration health probing and delivery monitoring."""

import smtplib
import ssl
import time
from typing import Any

from fastapi import Request
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.routes.health import database_status
from app.core.config import get_settings
from app.models import EmailDelivery, IntegrationProbeResult, SmsDelivery, User, WebhookDelivery
from app.models.base import utcnow
from app.services import audit
from app.services.http_client import request_json_with_retry
from app.services.lms_adapter import get_lms_integration_status
from app.services.ocr_pipeline import resolve_tesseract_cmd
from app.services.platform_config import get_effective_integrations_config, get_effective_lms_config
from app.services.sms import get_sms_integration_status
from app.services.storage import get_storage
from app.services.verification_providers import get_verification_integration_statuses, get_webhook_integration_status


def _probe_http_endpoint(
    url: str | None, *, auth_token: str | None = None, timeout_s: float = 4.0
) -> tuple[str, int | None, int, str]:
    if not url:
        return "NOT_CONFIGURED", None, 0, "Endpoint URL is not configured."
    headers = {"Authorization": f"Bearer {auth_token}"} if auth_token else None
    res = request_json_with_retry(
        "GET",
        url,
        headers=headers,
        timeout_seconds=timeout_s,
        max_retries=0,
        backoff_base_seconds=0.0,
    )
    if res.ok or (res.status_code is not None and res.status_code in {400, 401, 403, 404, 405}):
        # Reachable TLS/HTTP endpoint responded without network/5xx error
        return (
            "CONFIGURED",
            res.status_code,
            res.latency_ms,
            f"Endpoint reachable (HTTP {res.status_code}, {res.latency_ms} ms).",
        )
    return "DEGRADED", res.status_code, res.latency_ms, res.error_message or "Endpoint probe failed."


def _probe_smtp() -> tuple[str, str, int | None, str]:
    s = get_settings()
    if s.resend_api_key and s.email_from:
        return "CONFIGURED", "LIVE", 0, "Resend HTTPS API configured."
    if not s.email_configured or not s.smtp_host:
        return "NOT_CONFIGURED", "NONE", None, "Set SMTP_HOST (or RESEND_API_KEY) and EMAIL_FROM to enable email delivery."
    local_hosts = {"localhost", "127.0.0.1", "mailpit"}
    mode = "LOCAL_DEVELOPMENT" if s.smtp_host in local_hosts else "LIVE"
    started = time.perf_counter()
    try:
        if s.smtp_ssl:
            srv: smtplib.SMTP = smtplib.SMTP_SSL(
                s.smtp_host, s.smtp_port, timeout=min(4, s.smtp_timeout_seconds), context=ssl.create_default_context()
            )
        else:
            srv = smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=min(4, s.smtp_timeout_seconds))
        with srv:
            if s.smtp_starttls and not s.smtp_ssl:
                srv.starttls(context=ssl.create_default_context())
            srv.noop()
        ms = int((time.perf_counter() - started) * 1000)
        return "CONFIGURED", mode, ms, f"SMTP handshake & NOOP succeeded ({s.smtp_host}:{s.smtp_port}, {ms} ms)."
    except Exception as exc:  # noqa: BLE001
        ms = int((time.perf_counter() - started) * 1000)
        return "DEGRADED", mode, ms, f"SMTP probe failed ({type(exc).__name__})."


def probe_integrations(
    db: Session,
    request: Request,
    *,
    actor: User,
    target_key: str | None = None,
) -> list[dict[str, Any]]:
    cfg = get_effective_integrations_config(db)
    lms_cfg = get_effective_lms_config(db)
    timeout_s = min(4.0, float(cfg.integration_http_timeout_seconds))

    candidates: dict[str, dict[str, Any]] = {}

    # Database probe
    t0 = time.perf_counter()
    db_st = database_status()
    db_ms = int((time.perf_counter() - t0) * 1000)
    candidates["database"] = {
        "status": "CONFIGURED" if db_st.get("connected") else "DEGRADED",
        "mode": "LIVE",
        "latency_ms": db_ms,
        "http_status": None,
        "detail": f"PostgreSQL connected; migration={db_st.get('migration')}.",
    }

    # Storage probe
    t0 = time.perf_counter()
    try:
        st = get_storage().status()
        candidates["storage"] = {
            "status": "CONFIGURED" if st.configured else "NOT_CONFIGURED",
            "mode": "LOCAL_DEVELOPMENT" if st.mode == "LOCAL_DEVELOPMENT" else ("LIVE" if st.configured else "NONE"),
            "latency_ms": int((time.perf_counter() - t0) * 1000),
            "http_status": None,
            "detail": st.detail,
        }
    except Exception as exc:  # noqa: BLE001
        candidates["storage"] = {
            "status": "DEGRADED",
            "mode": "NONE",
            "latency_ms": int((time.perf_counter() - t0) * 1000),
            "http_status": None,
            "detail": f"Storage error: {type(exc).__name__}",
        }

    # Email SMTP probe
    em_status, em_mode, em_ms, em_detail = _probe_smtp()
    candidates["email"] = {
        "status": em_status,
        "mode": em_mode,
        "latency_ms": em_ms,
        "http_status": None,
        "detail": em_detail,
    }

    # IFSC directory probe
    if cfg.ifsc_lookup_enabled:
        st, code, ms, det = _probe_http_endpoint("https://ifsc.razorpay.com/HDFC0000240", timeout_s=timeout_s)
        candidates["ifsc_directory"] = {
            "status": st,
            "mode": "LIVE",
            "latency_ms": ms,
            "http_status": code,
            "detail": det,
        }
    else:
        candidates["ifsc_directory"] = {
            "status": "NOT_CONFIGURED",
            "mode": "NONE",
            "latency_ms": None,
            "http_status": None,
            "detail": "IFSC directory lookup disabled by configuration.",
        }

    # OCR probe
    if cfg.ocr_provider == "none":
        candidates["ocr"] = {
            "status": "NOT_CONFIGURED",
            "mode": "NONE",
            "latency_ms": None,
            "http_status": None,
            "detail": "OCR disabled.",
        }
    elif cfg.ocr_provider == "http_ocr":
        if cfg.ocr_api_base_url and cfg.ocr_api_key:
            st, code, ms, det = _probe_http_endpoint(
                cfg.ocr_api_base_url, auth_token=cfg.ocr_api_key, timeout_s=timeout_s
            )
            candidates["ocr"] = {"status": st, "mode": "LIVE", "latency_ms": ms, "http_status": code, "detail": det}
        else:
            candidates["ocr"] = {
                "status": "NOT_CONFIGURED",
                "mode": "NONE",
                "latency_ms": None,
                "http_status": None,
                "detail": "HTTP OCR URL or key missing.",
            }
    else:
        cmd = resolve_tesseract_cmd()
        candidates["ocr"] = {
            "status": "CONFIGURED" if cmd else "DEGRADED",
            "mode": "LOCAL_DEVELOPMENT",
            "latency_ms": 0,
            "http_status": None,
            "detail": f"Tesseract binary: {cmd}" if cmd else "Tesseract binary missing from PATH.",
        }

    # HTTP vendor probes (PAN, Bank, DigiLocker, Face, LMS, SMS)
    vendor_specs = (
        ("pan_verification", cfg.pan_verification_provider, cfg.pan_api_base_url, cfg.pan_api_key),
        ("bank_verification", cfg.bank_verification_provider, cfg.bank_api_base_url, cfg.bank_api_key),
        (
            "digilocker",
            cfg.digilocker_provider,
            cfg.digilocker_base_url,
            cfg.digilocker_client_secret if cfg.digilocker_client_id else None,
        ),
        ("face_match", cfg.face_match_provider, cfg.face_api_base_url, cfg.face_api_key),
        ("sms", cfg.sms_provider, cfg.sms_api_base_url, cfg.sms_api_key),
        ("lms", lms_cfg.lms_provider, lms_cfg.lms_api_base_url, lms_cfg.lms_api_key),
    )
    for k, prov, url, token in vendor_specs:
        if prov == "not_configured":
            candidates[k] = {
                "status": "NOT_CONFIGURED",
                "mode": "NONE",
                "latency_ms": None,
                "http_status": None,
                "detail": "Not configured.",
            }
        elif prov == "sandbox":
            candidates[k] = {
                "status": "CONFIGURED",
                "mode": "SANDBOX",
                "latency_ms": 0,
                "http_status": None,
                "detail": "Non-production sandbox fixture.",
            }
        elif not url or not token:
            candidates[k] = {
                "status": "NOT_CONFIGURED",
                "mode": "NONE",
                "latency_ms": None,
                "http_status": None,
                "detail": f"Provider '{prov}' selected but URL or credentials missing.",
            }
        else:
            st, code, ms, det = _probe_http_endpoint(url, auth_token=token, timeout_s=timeout_s)
            candidates[k] = {"status": st, "mode": "LIVE", "latency_ms": ms, "http_status": code, "detail": det}

    # AI Assistant & Webhooks summary
    ver_map = {row["key"]: row for row in get_verification_integration_statuses(db)}
    if "ai_assistant" in ver_map:
        ai = ver_map["ai_assistant"]
        candidates["ai_assistant"] = {
            "status": ai["status"],
            "mode": ai["mode"],
            "latency_ms": None,
            "http_status": None,
            "detail": ai["detail"],
        }
    wh = get_webhook_integration_status(db)
    candidates["webhooks"] = {
        "status": wh["status"],
        "mode": wh["mode"],
        "latency_ms": None,
        "http_status": None,
        "detail": wh["detail"],
    }

    selected = {target_key: candidates[target_key]} if target_key and target_key in candidates else candidates
    now = utcnow()
    output: list[dict[str, Any]] = []
    for k, info in selected.items():
        row = db.get(IntegrationProbeResult, k)
        if row is None:
            row = IntegrationProbeResult(adapter_key=k, **info, checked_at=now, checked_by_user_id=actor.id)
            db.add(row)
        else:
            row.status = info["status"]
            row.mode = info["mode"]
            row.latency_ms = info["latency_ms"]
            row.http_status = info["http_status"]
            row.detail = info["detail"]
            row.checked_at = now
            row.checked_by_user_id = actor.id
        output.append({"adapter_key": k, **info, "checked_at": now})

    audit.add(
        db,
        request,
        "admin.integrations.probed",
        actor=actor,
        resource_type="integration_probe",
        resource_id=target_key or "ALL",
        details={"keys": sorted(selected.keys())},
    )
    db.commit()
    return output


def collect_all_integration_statuses(db: Session) -> list[dict[str, str]]:
    """Shared integration status collector used by system health and admin dashboard."""
    lms_st = get_lms_integration_status(db)
    sms_st = get_sms_integration_status(db)
    wh_st = get_webhook_integration_status(db)
    return get_verification_integration_statuses(db) + [
        {
            "key": lms_st["key"],
            "name": lms_st["name"],
            "status": lms_st["status"],
            "mode": lms_st["mode"],
            "detail": lms_st["detail"],
        },
        sms_st,
        wh_st,
    ]


def get_integrations_monitor(db: Session) -> dict[str, Any]:
    probes = db.scalars(select(IntegrationProbeResult).order_by(IntegrationProbeResult.adapter_key.asc())).all()
    emails = db.scalars(select(EmailDelivery).order_by(desc(EmailDelivery.created_at)).limit(25)).all()
    sms_rows = db.scalars(select(SmsDelivery).order_by(desc(SmsDelivery.created_at)).limit(25)).all()
    webhooks = db.scalars(select(WebhookDelivery).order_by(desc(WebhookDelivery.received_at)).limit(25)).all()
    return {
        "probes": probes,
        "email_deliveries": emails,
        "sms_deliveries": sms_rows,
        "webhook_deliveries": webhooks,
    }
