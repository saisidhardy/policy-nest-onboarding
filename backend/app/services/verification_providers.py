"""External verification provider adapters with strict provenance labelling.

Clearly distinguishes:
- PUBLIC_DIRECTORY (live Razorpay public IFSC directory mirror)
- SANDBOX (non-production only, explicitly flagged is_simulated=True, provider_reference=None)
- REAL_PROVIDER (authorized commercial/government integration boundary over HTTPS with retries)
- UNCONFIGURED (honestly reports NOT_CONFIGURED without fabricating responses)
"""

import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.http_client import request_json_with_retry
from app.services.platform_config import EffectiveIntegrationsConfig, get_effective_integrations_config

IFSC_RE = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")


@dataclass(frozen=True)
class ProviderCheckResult:
    check_type: str
    target_doc_type: str | None
    status: str  # PASSED | WARN | FAILED | NOT_CONFIGURED | UNAVAILABLE
    origin: str  # PUBLIC_DIRECTORY | SANDBOX | REAL_PROVIDER | UNCONFIGURED
    provider_name: str
    provider_reference: str | None
    is_simulated: bool
    confidence: float | None
    details: dict
    explanation: str


def _extract_vendor_ref(data: dict[str, Any]) -> str | None:
    for key in ("reference_id", "transaction_id", "request_id", "utr", "verification_id", "id"):
        val = data.get(key)
        if val:
            return str(val)[:128]
    return None


def _run_vendor_http_check(
    *,
    cfg: EffectiveIntegrationsConfig,
    check_type: str,
    target_doc_type: str | None,
    provider_name: str,
    base_url: str | None,
    auth_token: str | None,
    payload: dict[str, Any],
    missing_detail: str,
) -> ProviderCheckResult:
    if not base_url or not auth_token:
        return ProviderCheckResult(
            check_type=check_type,
            target_doc_type=target_doc_type,
            status="NOT_CONFIGURED",
            origin="UNCONFIGURED",
            provider_name=provider_name,
            provider_reference=None,
            is_simulated=False,
            confidence=None,
            details={"selected_provider": provider_name, "missing_credentials": True},
            explanation=missing_detail,
        )

    res = request_json_with_retry(
        "POST",
        base_url,
        headers={"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"},
        json_body=payload,
        timeout_seconds=float(cfg.integration_http_timeout_seconds),
        max_retries=cfg.integration_http_max_retries,
        backoff_base_seconds=0.1,
    )
    if not res.ok:
        return ProviderCheckResult(
            check_type=check_type,
            target_doc_type=target_doc_type,
            status="UNAVAILABLE",
            origin="REAL_PROVIDER",
            provider_name=provider_name,
            provider_reference=None,
            is_simulated=False,
            confidence=None,
            details={"error_code": res.error_code, "attempts": res.attempts, "latency_ms": res.latency_ms},
            explanation=f"Authorized provider '{provider_name}' unavailable: {res.error_message}",
        )

    verified_raw = res.data.get("verified")
    vendor_status = str(res.data.get("status") or "").upper()
    if verified_raw is True or vendor_status in {"PASSED", "VALID", "VERIFIED", "MATCH", "SUCCESS"}:
        mapped_status = "PASSED"
    elif verified_raw is False or vendor_status in {"FAILED", "INVALID", "REJECTED", "MISMATCH"}:
        mapped_status = "FAILED"
    elif vendor_status == "PENDING":
        mapped_status = "WARN"
    else:
        mapped_status = "WARN"

    raw_conf = res.data.get("confidence") if "confidence" in res.data else res.data.get("similarity")
    conf = float(raw_conf) if isinstance(raw_conf, int | float) else None
    ref = _extract_vendor_ref(res.data)
    return ProviderCheckResult(
        check_type=check_type,
        target_doc_type=target_doc_type,
        status=mapped_status,
        origin="REAL_PROVIDER",
        provider_name=provider_name,
        provider_reference=ref,
        is_simulated=False,
        confidence=conf,
        details={
            "latency_ms": res.latency_ms,
            "attempts": res.attempts,
            "vendor_status": vendor_status or None,
        },
        explanation=str(
            res.data.get("message")
            or f"Verified via authorized provider '{provider_name}' (ref: {ref or 'none returned'})."
        ),
    )


def lookup_ifsc_directory(ifsc_code: str | None, db: Session | None = None) -> ProviderCheckResult:
    cfg = get_effective_integrations_config(db)
    if not cfg.ifsc_lookup_enabled:
        return ProviderCheckResult(
            check_type="EXTERNAL_IFSC_DIRECTORY",
            target_doc_type="BANK_DOCUMENT",
            status="NOT_CONFIGURED",
            origin="UNCONFIGURED",
            provider_name="ifsc_directory",
            provider_reference=None,
            is_simulated=False,
            confidence=None,
            details={},
            explanation="IFSC directory lookup is disabled in configuration.",
        )
    if not ifsc_code or not IFSC_RE.match(ifsc_code.strip().upper()):
        return ProviderCheckResult(
            check_type="EXTERNAL_IFSC_DIRECTORY",
            target_doc_type="BANK_DOCUMENT",
            status="WARN",
            origin="UNCONFIGURED",
            provider_name="razorpay_ifsc",
            provider_reference=None,
            is_simulated=False,
            confidence=None,
            details={"ifsc_code": ifsc_code},
            explanation="Valid IFSC required before directory lookup.",
        )

    code = ifsc_code.strip().upper()
    res = request_json_with_retry(
        "GET",
        f"https://ifsc.razorpay.com/{code}",
        timeout_seconds=min(4.0, float(cfg.integration_http_timeout_seconds)),
        max_retries=1,
        backoff_base_seconds=0.1,
    )
    if res.ok and res.data:
        payload = res.data
        return ProviderCheckResult(
            check_type="EXTERNAL_IFSC_DIRECTORY",
            target_doc_type="BANK_DOCUMENT",
            status="PASSED",
            origin="PUBLIC_DIRECTORY",
            provider_name="razorpay_ifsc_directory",
            provider_reference=code,
            is_simulated=False,
            confidence=1.0,
            details={
                "bank": payload.get("BANK"),
                "branch": payload.get("BRANCH"),
                "city": payload.get("CITY"),
                "state": payload.get("STATE"),
                "latency_ms": res.latency_ms,
            },
            explanation=f"Verified IFSC {code} via public RBI/Razorpay IFSC directory ({payload.get('BANK')} - {payload.get('BRANCH')}).",
        )
    if res.status_code == 404:
        return ProviderCheckResult(
            check_type="EXTERNAL_IFSC_DIRECTORY",
            target_doc_type="BANK_DOCUMENT",
            status="FAILED",
            origin="PUBLIC_DIRECTORY",
            provider_name="razorpay_ifsc_directory",
            provider_reference=None,
            is_simulated=False,
            confidence=1.0,
            details={"ifsc_code": code},
            explanation=f"IFSC code {code} was not found in the public IFSC directory.",
        )
    return ProviderCheckResult(
        check_type="EXTERNAL_IFSC_DIRECTORY",
        target_doc_type="BANK_DOCUMENT",
        status="UNAVAILABLE",
        origin="PUBLIC_DIRECTORY",
        provider_name="razorpay_ifsc_directory",
        provider_reference=None,
        is_simulated=False,
        confidence=None,
        details={"error_code": res.error_code},
        explanation="Public IFSC directory could not be reached right now.",
    )


def check_pan_verification_adapter(
    pan_number: str | None, *, full_name: str | None = None, db: Session | None = None
) -> ProviderCheckResult:
    cfg = get_effective_integrations_config(db)
    mode = cfg.pan_verification_provider
    if mode == "not_configured":
        return ProviderCheckResult(
            check_type="EXTERNAL_PAN",
            target_doc_type="PAN_CARD",
            status="NOT_CONFIGURED",
            origin="UNCONFIGURED",
            provider_name="pan_verification",
            provider_reference=None,
            is_simulated=False,
            confidence=None,
            details={},
            explanation="Authorized PAN registry provider (Protean/Cashfree) is not configured. Format checked locally only.",
        )
    if mode == "sandbox":
        if get_settings().app_env == "production":
            raise RuntimeError("Sandbox PAN adapter is forbidden in production")
        return ProviderCheckResult(
            check_type="EXTERNAL_PAN",
            target_doc_type="PAN_CARD",
            status="PASSED" if pan_number else "WARN",
            origin="SANDBOX",
            provider_name="pan_sandbox",
            provider_reference=None,
            is_simulated=True,
            confidence=None,
            details={"sandbox": True, "note": "Simulated non-production response"},
            explanation="SANDBOX: Simulated PAN holder verification (non-production only).",
        )
    if not pan_number:
        return ProviderCheckResult(
            check_type="EXTERNAL_PAN",
            target_doc_type="PAN_CARD",
            status="WARN",
            origin="UNCONFIGURED",
            provider_name=mode,
            provider_reference=None,
            is_simulated=False,
            confidence=None,
            details={},
            explanation="PAN number is required before querying authorized PAN registry.",
        )
    return _run_vendor_http_check(
        cfg=cfg,
        check_type="EXTERNAL_PAN",
        target_doc_type="PAN_CARD",
        provider_name=mode,
        base_url=cfg.pan_api_base_url,
        auth_token=cfg.pan_api_key,
        payload={"pan": pan_number, "name": full_name},
        missing_detail=f"PAN provider '{mode}' selected, but API base URL or API key is missing.",
    )


def check_bank_penny_drop_adapter(
    ifsc_code: str | None,
    holder_name: str | None,
    *,
    account_last4: str | None = None,
    db: Session | None = None,
) -> ProviderCheckResult:
    cfg = get_effective_integrations_config(db)
    mode = cfg.bank_verification_provider
    if mode == "not_configured":
        return ProviderCheckResult(
            check_type="EXTERNAL_BANK_PENNY_DROP",
            target_doc_type="BANK_DOCUMENT",
            status="NOT_CONFIGURED",
            origin="UNCONFIGURED",
            provider_name="bank_verification",
            provider_reference=None,
            is_simulated=False,
            confidence=None,
            details={},
            explanation="Authorized bank penny-drop provider (RazorpayX/Cashfree) is not configured. No live transfer performed.",
        )
    if mode == "sandbox":
        if get_settings().app_env == "production":
            raise RuntimeError("Sandbox bank adapter is forbidden in production")
        return ProviderCheckResult(
            check_type="EXTERNAL_BANK_PENNY_DROP",
            target_doc_type="BANK_DOCUMENT",
            status="PASSED" if (ifsc_code and holder_name) else "WARN",
            origin="SANDBOX",
            provider_name="bank_penny_drop_sandbox",
            provider_reference=None,
            is_simulated=True,
            confidence=None,
            details={"sandbox": True, "ifsc_code": ifsc_code},
            explanation="SANDBOX: Simulated IMPS penny-drop check (non-production only; no RRN fabricated).",
        )
    if not ifsc_code or not holder_name:
        return ProviderCheckResult(
            check_type="EXTERNAL_BANK_PENNY_DROP",
            target_doc_type="BANK_DOCUMENT",
            status="WARN",
            origin="UNCONFIGURED",
            provider_name=mode,
            provider_reference=None,
            is_simulated=False,
            confidence=None,
            details={},
            explanation="IFSC code and account holder name are required before penny-drop verification.",
        )
    return _run_vendor_http_check(
        cfg=cfg,
        check_type="EXTERNAL_BANK_PENNY_DROP",
        target_doc_type="BANK_DOCUMENT",
        provider_name=mode,
        base_url=cfg.bank_api_base_url,
        auth_token=cfg.bank_api_key,
        payload={"ifsc": ifsc_code, "account_holder_name": holder_name, "account_last4": account_last4},
        missing_detail=f"Bank verification provider '{mode}' selected, but API base URL or API key is missing.",
    )


def check_digilocker_adapter(*, application_id: str | None = None, db: Session | None = None) -> ProviderCheckResult:
    cfg = get_effective_integrations_config(db)
    mode = cfg.digilocker_provider
    if mode == "not_configured":
        return ProviderCheckResult(
            check_type="EXTERNAL_DIGILOCKER",
            target_doc_type=None,
            status="NOT_CONFIGURED",
            origin="UNCONFIGURED",
            provider_name="digilocker",
            provider_reference=None,
            is_simulated=False,
            confidence=None,
            details={},
            explanation="Authorized DigiLocker OAuth requester (MeitY/NeGD) is not configured.",
        )
    if mode == "sandbox":
        if get_settings().app_env == "production":
            raise RuntimeError("Sandbox DigiLocker adapter is forbidden in production")
        return ProviderCheckResult(
            check_type="EXTERNAL_DIGILOCKER",
            target_doc_type=None,
            status="PASSED",
            origin="SANDBOX",
            provider_name="digilocker_sandbox",
            provider_reference=None,
            is_simulated=True,
            confidence=None,
            details={"sandbox": True},
            explanation="SANDBOX: Simulated DigiLocker consent fixture (non-production only).",
        )
    if not (cfg.digilocker_base_url and cfg.digilocker_client_id and cfg.digilocker_client_secret):
        return ProviderCheckResult(
            check_type="EXTERNAL_DIGILOCKER",
            target_doc_type=None,
            status="NOT_CONFIGURED",
            origin="UNCONFIGURED",
            provider_name=mode,
            provider_reference=None,
            is_simulated=False,
            confidence=None,
            details={"selected_provider": mode, "missing_credentials": True},
            explanation=f"DigiLocker provider '{mode}' requires base URL, client ID, and client secret.",
        )
    return _run_vendor_http_check(
        cfg=cfg,
        check_type="EXTERNAL_DIGILOCKER",
        target_doc_type=None,
        provider_name=mode,
        base_url=cfg.digilocker_base_url,
        auth_token=cfg.digilocker_client_secret,
        payload={"client_id": cfg.digilocker_client_id, "application_id": application_id},
        missing_detail=f"DigiLocker '{mode}' credentials incomplete.",
    )


def check_face_match_adapter(
    face_detected: bool | None, *, application_id: str | None = None, db: Session | None = None
) -> ProviderCheckResult:
    cfg = get_effective_integrations_config(db)
    mode = cfg.face_match_provider
    if mode == "not_configured":
        return ProviderCheckResult(
            check_type="FACE_MATCH",
            target_doc_type="APPLICANT_SELFIE",
            status="NOT_CONFIGURED",
            origin="UNCONFIGURED",
            provider_name="face_match",
            provider_reference=None,
            is_simulated=False,
            confidence=None,
            details={"local_face_detected": face_detected},
            explanation="1:1 biometric face comparison & anti-spoof liveness provider is not configured. Local face presence checked only.",
        )
    if mode == "sandbox":
        if get_settings().app_env == "production":
            raise RuntimeError("Sandbox face-match adapter is forbidden in production")
        return ProviderCheckResult(
            check_type="FACE_MATCH",
            target_doc_type="APPLICANT_SELFIE",
            status="PASSED" if face_detected else "WARN",
            origin="SANDBOX",
            provider_name="face_match_sandbox",
            provider_reference=None,
            is_simulated=True,
            confidence=None,
            details={"sandbox": True, "local_face_detected": face_detected},
            explanation="SANDBOX: Simulated biometric comparison placeholder (no biometric score fabricated).",
        )
    return _run_vendor_http_check(
        cfg=cfg,
        check_type="FACE_MATCH",
        target_doc_type="APPLICANT_SELFIE",
        provider_name=mode,
        base_url=cfg.face_api_base_url,
        auth_token=cfg.face_api_key,
        payload={"application_id": application_id, "local_face_detected": face_detected},
        missing_detail=f"Face match provider '{mode}' selected, but API base URL or API key is missing.",
    )


def get_webhook_integration_status(db: Session | None = None) -> dict[str, str]:
    cfg = get_effective_integrations_config(db)
    if cfg.webhook_shared_secret:
        return {
            "key": "webhooks",
            "name": "Inbound vendor webhooks",
            "status": "CONFIGURED",
            "mode": "LIVE",
            "detail": "HMAC-SHA256 webhook verification active with idempotent event replay protection.",
        }
    return {
        "key": "webhooks",
        "name": "Inbound vendor webhooks",
        "status": "NOT_CONFIGURED",
        "mode": "NONE",
        "detail": "Webhook shared HMAC secret is not configured; inbound vendor callbacks will reject unsigned payloads.",
    }


def get_verification_integration_statuses(db: Session | None = None) -> list[dict[str, str]]:
    """Return honest live/local/sandbox/unconfigured status entries for Phase 3 & Phase 8 providers."""
    from app.services.ocr_pipeline import resolve_tesseract_cmd

    s = get_effective_integrations_config(db)
    statuses: list[dict[str, str]] = []

    if s.ocr_provider == "none":
        statuses.append(
            {
                "key": "ocr",
                "name": "OCR & CV quality engine",
                "status": "NOT_CONFIGURED",
                "mode": "NONE",
                "detail": "OCR_PROVIDER=none; document text extraction is disabled.",
            }
        )
    elif s.ocr_provider == "http_ocr":
        has_ocr = bool(s.ocr_api_base_url and s.ocr_api_key)
        statuses.append(
            {
                "key": "ocr",
                "name": "OCR & CV quality engine",
                "status": "CONFIGURED" if has_ocr else "NOT_CONFIGURED",
                "mode": "LIVE" if has_ocr else "NONE",
                "detail": (
                    f"External HTTP OCR adapter configured ({s.ocr_api_base_url})."
                    if has_ocr
                    else "HTTP OCR selected, but OCR API base URL or API key is missing."
                ),
            }
        )
    else:
        cmd = resolve_tesseract_cmd()
        statuses.append(
            {
                "key": "ocr",
                "name": "OCR & CV quality engine",
                "status": "CONFIGURED" if cmd else "DEGRADED",
                "mode": "LOCAL_DEVELOPMENT",
                "detail": (
                    f"Local Tesseract OCR ({cmd}) + OpenCV quality checks + PyPDF text extraction active."
                    if cmd
                    else "OpenCV quality and PyPDF text active; Tesseract OCR binary not found on PATH."
                ),
            }
        )

    if s.ai_provider == "gemini":
        if bool(s.gemini_api_key):
            statuses.append(
                {
                    "key": "ai_assistant",
                    "name": "AI extraction assistant (advisory)",
                    "status": "CONFIGURED",
                    "mode": "LIVE",
                    "detail": f"Gemini advisory assistant ({s.gemini_model}) enabled; deterministic rules control decisions.",
                }
            )
        else:
            statuses.append(
                {
                    "key": "ai_assistant",
                    "name": "AI extraction assistant (advisory)",
                    "status": "DEGRADED",
                    "mode": "LOCAL_DEVELOPMENT",
                    "detail": "AI_PROVIDER=gemini but GEMINI_API_KEY is missing; using local deterministic explanations.",
                }
            )
    else:
        statuses.append(
            {
                "key": "ai_assistant",
                "name": "AI extraction assistant (advisory)",
                "status": "CONFIGURED",
                "mode": "LOCAL_DEVELOPMENT",
                "detail": "Local deterministic explanation adapter active (advisory only).",
            }
        )

    statuses.append(
        {
            "key": "ifsc_directory",
            "name": "Public RBI / Razorpay IFSC directory",
            "status": "CONFIGURED" if s.ifsc_lookup_enabled else "NOT_CONFIGURED",
            "mode": "LIVE" if s.ifsc_lookup_enabled else "NONE",
            "detail": (
                "Public IFSC directory lookups active against https://ifsc.razorpay.com."
                if s.ifsc_lookup_enabled
                else "Public IFSC directory lookup disabled by IFSC_LOOKUP_ENABLED=false."
            ),
        }
    )

    vendor_configs = (
        (
            "pan_verification",
            "PAN verification (Protean/Cashfree)",
            s.pan_verification_provider,
            bool(s.pan_api_base_url and s.pan_api_key),
            s.pan_api_base_url,
        ),
        (
            "bank_verification",
            "Bank account penny-drop verification",
            s.bank_verification_provider,
            bool(s.bank_api_base_url and s.bank_api_key),
            s.bank_api_base_url,
        ),
        (
            "digilocker",
            "DigiLocker document source",
            s.digilocker_provider,
            bool(s.digilocker_base_url and s.digilocker_client_id and s.digilocker_client_secret),
            s.digilocker_base_url,
        ),
        (
            "face_match",
            "Face match and liveness",
            s.face_match_provider,
            bool(s.face_api_base_url and s.face_api_key),
            s.face_api_base_url,
        ),
    )

    for key, label, provider_val, creds_ok, endpoint in vendor_configs:
        if provider_val == "not_configured":
            statuses.append(
                {
                    "key": key,
                    "name": label,
                    "status": "NOT_CONFIGURED",
                    "mode": "NONE",
                    "detail": "Authorized provider credentials not configured. Local format/presence checks only.",
                }
            )
        elif provider_val == "sandbox":
            statuses.append(
                {
                    "key": key,
                    "name": label,
                    "status": "CONFIGURED",
                    "mode": "SANDBOX",
                    "detail": "Non-production sandbox fixture active (explicitly marked is_simulated=true).",
                }
            )
        elif creds_ok:
            statuses.append(
                {
                    "key": key,
                    "name": label,
                    "status": "CONFIGURED",
                    "mode": "LIVE",
                    "detail": f"Authorized provider '{provider_val}' configured ({endpoint}).",
                }
            )
        else:
            statuses.append(
                {
                    "key": key,
                    "name": label,
                    "status": "NOT_CONFIGURED",
                    "mode": "NONE",
                    "detail": f"Provider '{provider_val}' selected, but endpoint URL or credentials are missing.",
                }
            )

    return statuses
