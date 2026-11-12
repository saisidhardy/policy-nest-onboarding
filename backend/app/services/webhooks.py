"""Unified inbound signed webhook verification, idempotency, and persistence."""

import hashlib
import hmac
import json
import uuid
from typing import Any

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import constant_time_equals
from app.models import Application, ApplicationEvent, VerificationCheck, WebhookDelivery
from app.models.base import utcnow
from app.services import audit
from app.services.platform_config import get_effective_integrations_config

SOURCE_CHECK_TYPE = {
    "pan": ("EXTERNAL_PAN", "PAN_CARD"),
    "bank": ("EXTERNAL_BANK_PENNY_DROP", "BANK_DOCUMENT"),
    "digilocker": ("EXTERNAL_DIGILOCKER", None),
}

VENDOR_STATUS_MAP = {
    "PASSED": "PASSED",
    "VALID": "PASSED",
    "VERIFIED": "PASSED",
    "SUCCESS": "PASSED",
    "MATCH": "PASSED",
    "FAILED": "FAILED",
    "INVALID": "FAILED",
    "REJECTED": "FAILED",
    "MISMATCH": "FAILED",
    "WARN": "WARN",
    "PENDING": "WARN",
}


def verify_hmac_sha256(raw_body: bytes, signature_header: str | None, secret: str | None) -> tuple[bool, str]:
    if not secret:
        return False, "Webhook shared HMAC secret is not configured."
    if not signature_header or not signature_header.strip():
        return False, "Missing webhook signature header."
    provided = signature_header.strip()
    if provided.lower().startswith("sha256="):
        provided = provided.split("=", 1)[1].strip()
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    if not constant_time_equals(provided.lower(), expected.lower()):
        return False, "Webhook HMAC signature mismatch."
    return True, "ok"


def _safe_json(raw_body: bytes) -> dict[str, Any]:
    try:
        parsed = json.loads(raw_body.decode("utf-8"))
        return parsed if isinstance(parsed, dict) else {"raw": parsed}
    except Exception:  # noqa: BLE001
        return {}


def record_lms_webhook_delivery(
    db: Session,
    *,
    raw_body: bytes,
    signature_valid: bool,
    processing_status: str,
    application_id: uuid.UUID | None = None,
    external_event_id: str | None = None,
    error_message: str | None = None,
) -> WebhookDelivery:
    row = WebhookDelivery(
        id=uuid.uuid4(),
        source="lms",
        external_event_id=external_event_id,
        signature_valid=signature_valid,
        processing_status=processing_status,
        application_id=application_id,
        payload=_safe_json(raw_body),
        error_message=error_message,
        processed_at=utcnow() if processing_status == "PROCESSED" else None,
    )
    db.add(row)
    db.flush()
    return row


def process_verification_webhook(
    db: Session,
    request: Request,
    *,
    source: str,
    raw_body: bytes,
    signature: str | None,
) -> dict[str, Any]:
    src = source.strip().lower()
    if src not in SOURCE_CHECK_TYPE:
        raise AppError(404, "UNKNOWN_WEBHOOK_SOURCE", f"Unsupported verification webhook source '{source}'.")

    cfg = get_effective_integrations_config(db)
    ok, sig_reason = verify_hmac_sha256(raw_body, signature, cfg.webhook_shared_secret)
    payload = _safe_json(raw_body)
    event_id_raw = payload.get("event_id") or payload.get("idempotency_key")
    event_id = str(event_id_raw)[:128] if event_id_raw else None

    if not ok:
        row = WebhookDelivery(
            id=uuid.uuid4(),
            source=src,
            external_event_id=None,
            signature_valid=False,
            processing_status="REJECTED_SIGNATURE",
            payload=payload,
            error_message=sig_reason,
        )
        db.add(row)
        db.commit()
        code = "WEBHOOK_SECRET_NOT_CONFIGURED" if not cfg.webhook_shared_secret else "INVALID_WEBHOOK_SIGNATURE"
        raise AppError(401, code, sig_reason)

    if not payload:
        raise AppError(400, "INVALID_WEBHOOK_JSON", "Webhook body must be a valid JSON object.")

    if event_id:
        existing = db.scalar(
            select(WebhookDelivery).where(WebhookDelivery.source == src, WebhookDelivery.external_event_id == event_id)
        )
        if existing is not None:
            return {
                "webhook_id": str(existing.id),
                "source": src,
                "processing_status": "DUPLICATE_IGNORED",
                "application_id": str(existing.application_id) if existing.application_id else None,
                "external_event_id": event_id,
            }

    app_row: Application | None = None
    if payload.get("application_id"):
        try:
            app_row = db.get(Application, uuid.UUID(str(payload["application_id"])))
        except ValueError:
            app_row = None
    if app_row is None and payload.get("reference_code"):
        app_row = db.scalar(
            select(Application).where(Application.reference_code == str(payload["reference_code"]).strip())
        )

    if app_row is None:
        row = WebhookDelivery(
            id=uuid.uuid4(),
            source=src,
            external_event_id=event_id,
            signature_valid=True,
            processing_status="UNMATCHED_ENTITY",
            payload=payload,
            error_message="No matching application found for webhook application_id/reference_code.",
            processed_at=utcnow(),
        )
        db.add(row)
        db.commit()
        raise AppError(404, "APPLICATION_NOT_FOUND", "No matching application found for webhook callback.")

    check_type, target_doc = SOURCE_CHECK_TYPE[src]
    raw_status = str(payload.get("status") or "").upper()
    mapped_status = VENDOR_STATUS_MAP.get(raw_status)
    if not mapped_status:
        row = WebhookDelivery(
            id=uuid.uuid4(),
            source=src,
            external_event_id=event_id,
            signature_valid=True,
            processing_status="FAILED",
            application_id=app_row.id,
            payload=payload,
            error_message=f"Unsupported vendor status '{raw_status}'.",
        )
        db.add(row)
        db.commit()
        raise AppError(400, "INVALID_VENDOR_STATUS", f"Unsupported vendor status '{raw_status}'.")

    ref_raw = payload.get("provider_reference") or payload.get("reference_id") or payload.get("transaction_id")
    provider_ref = str(ref_raw)[:128] if ref_raw else None
    provider_name = str(payload.get("provider_name") or src)[:64]
    raw_conf = payload.get("confidence") if "confidence" in payload else payload.get("similarity")
    conf = float(raw_conf) if isinstance(raw_conf, int | float) else None
    explanation = str(
        payload.get("explanation") or f"Async webhook update from '{provider_name}' marked check as {mapped_status}."
    )

    existing_check = db.scalar(
        select(VerificationCheck).where(
            VerificationCheck.application_id == app_row.id,
            VerificationCheck.check_type == check_type,
        )
    )
    if existing_check is None:
        existing_check = VerificationCheck(
            id=uuid.uuid4(),
            application_id=app_row.id,
            check_type=check_type,
            target_doc_type=target_doc,
            status=mapped_status,
            origin="REAL_PROVIDER",
            provider_name=provider_name,
            provider_reference=provider_ref,
            is_simulated=False,
            confidence=conf,
            details={"webhook_event_id": event_id, "vendor_status": raw_status},
            explanation=explanation,
        )
        db.add(existing_check)
    else:
        existing_check.status = mapped_status
        existing_check.origin = "REAL_PROVIDER"
        existing_check.provider_name = provider_name
        existing_check.provider_reference = provider_ref
        existing_check.is_simulated = False
        existing_check.confidence = conf
        existing_check.details = {"webhook_event_id": event_id, "vendor_status": raw_status}
        existing_check.explanation = explanation
        existing_check.checked_at = utcnow()

    db.add(
        ApplicationEvent(
            application_id=app_row.id,
            actor_user_id=None,
            actor_role="WEBHOOK",
            event_type="VENDOR_WEBHOOK_RECEIVED",
            from_status=app_row.status,
            to_status=app_row.status,
            summary=f"Received {src.upper()} webhook ({mapped_status})",
            details={"source": src, "external_event_id": event_id, "provider_reference": provider_ref},
        )
    )

    delivery = WebhookDelivery(
        id=uuid.uuid4(),
        source=src,
        external_event_id=event_id,
        signature_valid=True,
        processing_status="PROCESSED",
        application_id=app_row.id,
        payload=payload,
        processed_at=utcnow(),
    )
    db.add(delivery)
    audit.add(
        db,
        request,
        f"webhook.verification.{src}",
        resource_type="application",
        resource_id=str(app_row.id),
        details={"source": src, "status": mapped_status, "external_event_id": event_id},
    )
    db.commit()
    return {
        "webhook_id": str(delivery.id),
        "source": src,
        "processing_status": "PROCESSED",
        "application_id": str(app_row.id),
        "external_event_id": event_id,
    }
