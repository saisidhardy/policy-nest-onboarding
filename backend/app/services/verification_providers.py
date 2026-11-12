"""External verification provider adapters with strict provenance labelling.

Clearly distinguishes:
- PUBLIC_DIRECTORY (live Razorpay public IFSC directory mirror)
- SANDBOX (non-production only, explicitly flagged is_simulated=True, provider_reference=None)
- REAL_PROVIDER (authorized commercial/government integration boundary)
- UNCONFIGURED (honestly reports NOT_CONFIGURED without fabricating responses)
"""

import re
from dataclasses import dataclass

import httpx

from app.core.config import get_settings

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


def lookup_ifsc_directory(ifsc_code: str | None) -> ProviderCheckResult:
    s = get_settings()
    if not s.ifsc_lookup_enabled:
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
    try:
        resp = httpx.get(f"https://ifsc.razorpay.com/{code}", timeout=4.0)
        if resp.status_code == 200:
            payload = resp.json()
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
                },
                explanation=f"Verified IFSC {code} via public RBI/Razorpay IFSC directory ({payload.get('BANK')} - {payload.get('BRANCH')}).",
            )
        if resp.status_code == 404:
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
    except Exception as exc:  # noqa: BLE001
        return ProviderCheckResult(
            check_type="EXTERNAL_IFSC_DIRECTORY",
            target_doc_type="BANK_DOCUMENT",
            status="UNAVAILABLE",
            origin="PUBLIC_DIRECTORY",
            provider_name="razorpay_ifsc_directory",
            provider_reference=None,
            is_simulated=False,
            confidence=None,
            details={"error": type(exc).__name__},
            explanation="Public IFSC directory could not be reached right now.",
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
        details={},
        explanation="Public IFSC directory returned an unexpected response.",
    )


def check_pan_verification_adapter(pan_number: str | None) -> ProviderCheckResult:
    s = get_settings()
    mode = s.pan_verification_provider
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
        if s.app_env == "production":
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
    return ProviderCheckResult(
        check_type="EXTERNAL_PAN",
        target_doc_type="PAN_CARD",
        status="NOT_CONFIGURED",
        origin="UNCONFIGURED",
        provider_name=mode,
        provider_reference=None,
        is_simulated=False,
        confidence=None,
        details={"selected_provider": mode},
        explanation=f"Provider '{mode}' credentials are scheduled for Phase 8 completion.",
    )


def check_bank_penny_drop_adapter(ifsc_code: str | None, holder_name: str | None) -> ProviderCheckResult:
    s = get_settings()
    mode = s.bank_verification_provider
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
        if s.app_env == "production":
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
    return ProviderCheckResult(
        check_type="EXTERNAL_BANK_PENNY_DROP",
        target_doc_type="BANK_DOCUMENT",
        status="NOT_CONFIGURED",
        origin="UNCONFIGURED",
        provider_name=mode,
        provider_reference=None,
        is_simulated=False,
        confidence=None,
        details={"selected_provider": mode},
        explanation=f"Provider '{mode}' credentials are scheduled for Phase 8 completion.",
    )


def check_digilocker_adapter() -> ProviderCheckResult:
    s = get_settings()
    mode = s.digilocker_provider
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
        if s.app_env == "production":
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
    return ProviderCheckResult(
        check_type="EXTERNAL_DIGILOCKER",
        target_doc_type=None,
        status="NOT_CONFIGURED",
        origin="UNCONFIGURED",
        provider_name=mode,
        provider_reference=None,
        is_simulated=False,
        confidence=None,
        details={"selected_provider": mode},
        explanation=f"DigiLocker '{mode}' integration scheduled for Phase 8 completion.",
    )


def check_face_match_adapter(face_detected: bool | None) -> ProviderCheckResult:
    s = get_settings()
    mode = s.face_match_provider
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
        if s.app_env == "production":
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
    return ProviderCheckResult(
        check_type="FACE_MATCH",
        target_doc_type="APPLICANT_SELFIE",
        status="NOT_CONFIGURED",
        origin="UNCONFIGURED",
        provider_name=mode,
        provider_reference=None,
        is_simulated=False,
        confidence=None,
        details={"selected_provider": mode},
        explanation=f"Face match '{mode}' integration scheduled for Phase 8 completion.",
    )


def get_verification_integration_statuses() -> list[dict[str, str]]:
    """Return honest live/local/sandbox/unconfigured status entries for Phase 3 & verification providers."""
    from app.services.ai_assistant import get_ai_assistant
    from app.services.ocr_pipeline import resolve_tesseract_cmd

    s = get_settings()
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

    assistant = get_ai_assistant()
    if s.ai_provider == "gemini":
        if assistant.provider_name == "GEMINI":
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

    for key, label, provider_val in (
        ("pan_verification", "PAN verification (Protean/UTIITSL via authorised provider)", s.pan_verification_provider),
        ("bank_verification", "Bank account penny-drop verification", s.bank_verification_provider),
        ("digilocker", "DigiLocker document source", s.digilocker_provider),
        ("face_match", "Face match and liveness", s.face_match_provider),
    ):
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
        else:
            statuses.append(
                {
                    "key": key,
                    "name": label,
                    "status": "NOT_CONFIGURED",
                    "mode": "NONE",
                    "detail": f"Provider '{provider_val}' integration boundary scheduled for Phase 8 completion.",
                }
            )

    return statuses
