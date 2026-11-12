"""Phase 8 SMS notification adapter with strict provenance, retry/timeout handling, and DB persistence."""

import uuid
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import SmsDelivery
from app.models.base import utcnow
from app.services.http_client import request_json_with_retry
from app.services.platform_config import EffectiveIntegrationsConfig, get_effective_integrations_config

SMS_STATUS_SENT = "SENT"
SMS_STATUS_FAILED = "FAILED"
SMS_STATUS_NOT_CONFIGURED = "NOT_CONFIGURED"
SMS_STATUS_SANDBOX = "SANDBOX_SIMULATED"


def get_sms_integration_status(db: Session | None = None) -> dict[str, str]:
    cfg = get_effective_integrations_config(db)
    if cfg.sms_provider == "not_configured":
        return {
            "key": "sms",
            "name": "SMS notifications gateway",
            "status": "NOT_CONFIGURED",
            "mode": "NONE",
            "detail": "SMS gateway not configured. Set SMS provider, API base URL, and credentials to enable SMS alerts.",
        }
    if cfg.sms_provider == "sandbox":
        return {
            "key": "sms",
            "name": "SMS notifications gateway",
            "status": "CONFIGURED",
            "mode": "SANDBOX",
            "detail": "Non-production SMS sandbox fixture active (messages marked is_simulated=true; never sent to carriers).",
        }
    has_creds = bool(cfg.sms_api_base_url and cfg.sms_api_key)
    if not has_creds:
        return {
            "key": "sms",
            "name": "SMS notifications gateway",
            "status": "NOT_CONFIGURED",
            "mode": "NONE",
            "detail": f"SMS provider '{cfg.sms_provider}' selected, but API base URL or API key is missing.",
        }
    return {
        "key": "sms",
        "name": "SMS notifications gateway",
        "status": "CONFIGURED",
        "mode": "LIVE",
        "detail": f"SMS gateway '{cfg.sms_provider}' configured ({cfg.sms_api_base_url}).",
    }


def _dispatch_http_sms(
    cfg: EffectiveIntegrationsConfig, mobile: str, message: str, event_type: str
) -> tuple[str, int, str | None, str | None]:
    headers = {
        "Authorization": f"Bearer {cfg.sms_api_key}",
        "Content-Type": "application/json",
    }
    payload: dict[str, Any] = {
        "to": mobile,
        "message": message,
        "event_type": event_type,
        "provider": cfg.sms_provider,
    }
    if cfg.sms_sender_id:
        payload["sender_id"] = cfg.sms_sender_id

    res = request_json_with_retry(
        "POST",
        cfg.sms_api_base_url or "",
        headers=headers,
        json_body=payload,
        timeout_seconds=float(cfg.sms_timeout_seconds),
        max_retries=max(0, cfg.sms_max_attempts - 1),
        backoff_base_seconds=0.1,
    )
    if res.ok:
        msg_id = res.data.get("message_id") or res.data.get("sid") or res.data.get("request_id")
        return SMS_STATUS_SENT, res.attempts, str(msg_id) if msg_id else None, None
    return SMS_STATUS_FAILED, res.attempts, None, res.error_message


def send_sms_notification(
    db: Session,
    *,
    mobile: str | None,
    event_type: str,
    message: str,
    user_id: uuid.UUID | None = None,
    application_id: uuid.UUID | None = None,
) -> SmsDelivery | None:
    if not mobile or not mobile.strip():
        return None
    clean_mobile = mobile.strip()
    cfg = get_effective_integrations_config(db)
    preview = message.strip()[:320]

    if cfg.sms_provider == "sandbox":
        if get_settings().app_env == "production":
            raise RuntimeError("Sandbox SMS adapter is forbidden in production")
        row = SmsDelivery(
            id=uuid.uuid4(),
            user_id=user_id,
            application_id=application_id,
            recipient_mobile=clean_mobile,
            event_type=event_type,
            body_preview=preview,
            provider="sandbox",
            status=SMS_STATUS_SANDBOX,
            is_simulated=True,
            provider_message_id=None,
            attempts=1,
            sent_at=utcnow(),
        )
        db.add(row)
        db.flush()
        return row

    if cfg.sms_provider == "not_configured" or not cfg.sms_api_base_url or not cfg.sms_api_key:
        reason = (
            "SMS provider is not configured."
            if cfg.sms_provider == "not_configured"
            else f"SMS provider '{cfg.sms_provider}' is missing API base URL or API key."
        )
        row = SmsDelivery(
            id=uuid.uuid4(),
            user_id=user_id,
            application_id=application_id,
            recipient_mobile=clean_mobile,
            event_type=event_type,
            body_preview=preview,
            provider=cfg.sms_provider,
            status=SMS_STATUS_NOT_CONFIGURED,
            is_simulated=False,
            provider_message_id=None,
            attempts=0,
            error=reason,
        )
        db.add(row)
        db.flush()
        return row

    status, attempts, provider_id, error = _dispatch_http_sms(cfg, clean_mobile, preview, event_type)
    row = SmsDelivery(
        id=uuid.uuid4(),
        user_id=user_id,
        application_id=application_id,
        recipient_mobile=clean_mobile,
        event_type=event_type,
        body_preview=preview,
        provider=cfg.sms_provider,
        status=status,
        is_simulated=False,
        provider_message_id=provider_id,
        attempts=attempts,
        error=error,
        sent_at=utcnow() if status == SMS_STATUS_SENT else None,
    )
    db.add(row)
    db.flush()
    return row


def retry_failed_sms(db: Session, *, limit: int = 20) -> dict[str, int]:
    cfg = get_effective_integrations_config(db)
    if cfg.sms_provider == "not_configured" or (
        cfg.sms_provider != "sandbox" and not (cfg.sms_api_base_url and cfg.sms_api_key)
    ):
        return {"attempted": 0, "succeeded": 0, "failed": 0}

    rows = db.scalars(
        select(SmsDelivery)
        .where(SmsDelivery.status == SMS_STATUS_FAILED)
        .order_by(desc(SmsDelivery.created_at))
        .limit(limit)
    ).all()

    succeeded = 0
    failed = 0
    for row in rows:
        if cfg.sms_provider == "sandbox":
            if get_settings().app_env == "production":
                raise RuntimeError("Sandbox SMS adapter is forbidden in production")
            row.status = SMS_STATUS_SANDBOX
            row.is_simulated = True
            row.attempts += 1
            row.error = None
            row.sent_at = utcnow()
            succeeded += 1
            continue

        status, attempts, provider_id, error = _dispatch_http_sms(
            cfg, row.recipient_mobile, row.body_preview, row.event_type
        )
        row.provider = cfg.sms_provider
        row.attempts += attempts
        row.status = status
        row.provider_message_id = provider_id
        row.error = error
        if status == SMS_STATUS_SENT:
            row.sent_at = utcnow()
            succeeded += 1
        else:
            failed += 1

    db.flush()
    return {"attempted": len(rows), "succeeded": succeeded, "failed": failed}
