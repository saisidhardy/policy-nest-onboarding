"""Persistent runtime configuration resolution with Fernet-encrypted secret storage."""

import base64
import hashlib
from dataclasses import dataclass
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models import SystemConfig, User


def _fernet() -> Fernet:
    raw = hashlib.sha256(get_settings().secret_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(raw))


def encrypt_secret(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_secret(token: str | None) -> str | None:
    if not token:
        return None
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return None


def mask_secret_hint(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) <= 4:
        return "••••"
    return f"••••{value[-4:]}"


def _resolve_secret(sec: dict[str, Any], key: str, env_default: str | None) -> str | None:
    if key in sec:
        return decrypt_secret(sec.get(key))
    return env_default


@dataclass(frozen=True)
class EffectiveLmsConfig:
    lms_provider: str
    lms_api_base_url: str | None
    lms_api_key: str | None
    lms_webhook_secret: str | None
    lms_timeout_seconds: int
    lms_course_code: str
    lms_required_hours: float
    lms_passing_score_pct: float
    lms_exam_cooldown_hours: int
    lms_certificate_validity_years: int
    lms_sync_retry_base_seconds: int
    lms_sync_max_attempts: int
    source: str  # "database" | "environment"


@dataclass(frozen=True)
class EffectiveIntegrationsConfig:
    ocr_provider: str
    ocr_api_base_url: str | None
    ocr_api_key: str | None
    ai_provider: str
    gemini_model: str
    gemini_api_key: str | None
    ifsc_lookup_enabled: bool
    pan_verification_provider: str
    pan_api_base_url: str | None
    pan_api_key: str | None
    bank_verification_provider: str
    bank_api_base_url: str | None
    bank_api_key: str | None
    digilocker_provider: str
    digilocker_base_url: str | None
    digilocker_client_id: str | None
    digilocker_client_secret: str | None
    face_match_provider: str
    face_api_base_url: str | None
    face_api_key: str | None
    sms_provider: str
    sms_api_base_url: str | None
    sms_api_key: str | None
    sms_sender_id: str | None
    sms_timeout_seconds: int
    sms_max_attempts: int
    webhook_shared_secret: str | None
    integration_http_timeout_seconds: int
    integration_http_max_retries: int
    source: str


@dataclass(frozen=True)
class EffectivePlatformConfig:
    public_app_url: str
    require_email_verification: bool
    session_idle_minutes: int
    login_max_failures: int
    login_lockout_minutes: int
    max_upload_size_mb: int
    source: str


def _row(db: Session | None, key: str) -> SystemConfig | None:
    if db is None:
        return None
    return db.get(SystemConfig, key)


def get_effective_lms_config(db: Session | None = None, s: Settings | None = None) -> EffectiveLmsConfig:
    s = s or get_settings()
    row = _row(db, "lms")
    cfg = row.config_json if row else {}
    sec = row.secrets_encrypted if row else {}
    return EffectiveLmsConfig(
        lms_provider=cfg.get("lms_provider", s.lms_provider),
        lms_api_base_url=cfg.get("lms_api_base_url", s.lms_api_base_url),
        lms_api_key=_resolve_secret(sec, "lms_api_key", s.lms_api_key),
        lms_webhook_secret=_resolve_secret(sec, "lms_webhook_secret", s.lms_webhook_secret),
        lms_timeout_seconds=int(cfg.get("lms_timeout_seconds", s.lms_timeout_seconds)),
        lms_course_code=str(cfg.get("lms_course_code", s.lms_course_code)),
        lms_required_hours=float(cfg.get("lms_required_hours", s.lms_required_hours)),
        lms_passing_score_pct=float(cfg.get("lms_passing_score_pct", s.lms_passing_score_pct)),
        lms_exam_cooldown_hours=int(cfg.get("lms_exam_cooldown_hours", s.lms_exam_cooldown_hours)),
        lms_certificate_validity_years=int(cfg.get("lms_certificate_validity_years", s.lms_certificate_validity_years)),
        lms_sync_retry_base_seconds=int(cfg.get("lms_sync_retry_base_seconds", s.lms_sync_retry_base_seconds)),
        lms_sync_max_attempts=int(cfg.get("lms_sync_max_attempts", s.lms_sync_max_attempts)),
        source="database" if row is not None else "environment",
    )


def get_effective_integrations_config(
    db: Session | None = None, s: Settings | None = None
) -> EffectiveIntegrationsConfig:
    s = s or get_settings()
    row = _row(db, "integrations")
    cfg = row.config_json if row else {}
    sec = row.secrets_encrypted if row else {}
    return EffectiveIntegrationsConfig(
        ocr_provider=cfg.get("ocr_provider", s.ocr_provider),
        ocr_api_base_url=cfg.get("ocr_api_base_url", s.ocr_api_base_url),
        ocr_api_key=_resolve_secret(sec, "ocr_api_key", s.ocr_api_key),
        ai_provider=cfg.get("ai_provider", s.ai_provider),
        gemini_model=cfg.get("gemini_model", s.gemini_model),
        gemini_api_key=_resolve_secret(sec, "gemini_api_key", s.gemini_api_key),
        ifsc_lookup_enabled=bool(cfg.get("ifsc_lookup_enabled", s.ifsc_lookup_enabled)),
        pan_verification_provider=cfg.get("pan_verification_provider", s.pan_verification_provider),
        pan_api_base_url=cfg.get("pan_api_base_url", s.pan_api_base_url),
        pan_api_key=_resolve_secret(sec, "pan_api_key", s.pan_api_key),
        bank_verification_provider=cfg.get("bank_verification_provider", s.bank_verification_provider),
        bank_api_base_url=cfg.get("bank_api_base_url", s.bank_api_base_url),
        bank_api_key=_resolve_secret(sec, "bank_api_key", s.bank_api_key),
        digilocker_provider=cfg.get("digilocker_provider", s.digilocker_provider),
        digilocker_base_url=cfg.get("digilocker_base_url", s.digilocker_base_url),
        digilocker_client_id=cfg.get("digilocker_client_id", s.digilocker_client_id),
        digilocker_client_secret=_resolve_secret(sec, "digilocker_client_secret", s.digilocker_client_secret),
        face_match_provider=cfg.get("face_match_provider", s.face_match_provider),
        face_api_base_url=cfg.get("face_api_base_url", s.face_api_base_url),
        face_api_key=_resolve_secret(sec, "face_api_key", s.face_api_key),
        sms_provider=cfg.get("sms_provider", s.sms_provider),
        sms_api_base_url=cfg.get("sms_api_base_url", s.sms_api_base_url),
        sms_api_key=_resolve_secret(sec, "sms_api_key", s.sms_api_key),
        sms_sender_id=cfg.get("sms_sender_id", s.sms_sender_id),
        sms_timeout_seconds=int(cfg.get("sms_timeout_seconds", s.sms_timeout_seconds)),
        sms_max_attempts=int(cfg.get("sms_max_attempts", s.sms_max_attempts)),
        webhook_shared_secret=_resolve_secret(sec, "webhook_shared_secret", s.webhook_shared_secret),
        integration_http_timeout_seconds=int(
            cfg.get("integration_http_timeout_seconds", s.integration_http_timeout_seconds)
        ),
        integration_http_max_retries=int(cfg.get("integration_http_max_retries", s.integration_http_max_retries)),
        source="database" if row is not None else "environment",
    )


def get_effective_platform_config(db: Session | None = None, s: Settings | None = None) -> EffectivePlatformConfig:
    s = s or get_settings()
    row = _row(db, "platform")
    cfg = row.config_json if row else {}
    return EffectivePlatformConfig(
        public_app_url=str(cfg.get("public_app_url", s.public_app_url)),
        require_email_verification=bool(cfg.get("require_email_verification", s.require_email_verification)),
        session_idle_minutes=int(cfg.get("session_idle_minutes", s.session_idle_minutes)),
        login_max_failures=int(cfg.get("login_max_failures", s.login_max_failures)),
        login_lockout_minutes=int(cfg.get("login_lockout_minutes", s.login_lockout_minutes)),
        max_upload_size_mb=int(cfg.get("max_upload_size_mb", s.max_upload_size_mb)),
        source="database" if row is not None else "environment",
    )


def upsert_section(
    db: Session,
    key: str,
    values: dict[str, Any],
    *,
    secret_updates: dict[str, str | None] | None = None,
    clear_secrets: list[str] | None = None,
    actor: User,
) -> tuple[SystemConfig, list[str]]:
    row = db.get(SystemConfig, key)
    if row is None:
        row = SystemConfig(key=key, config_json={}, secrets_encrypted={})
        db.add(row)

    merged_cfg = dict(row.config_json or {})
    merged_cfg.update(values)
    row.config_json = merged_cfg

    merged_secrets = dict(row.secrets_encrypted or {})
    touched_secrets: list[str] = []
    for sk in clear_secrets or []:
        merged_secrets[sk] = None
        touched_secrets.append(f"{sk}(cleared)")
    for sk, sv in (secret_updates or {}).items():
        if sv is not None and sv.strip():
            merged_secrets[sk] = encrypt_secret(sv.strip())
            touched_secrets.append(sk)
    row.secrets_encrypted = merged_secrets
    row.updated_by_user_id = actor.id
    db.flush()
    return row, touched_secrets


def reset_section(db: Session, key: str) -> bool:
    row = db.get(SystemConfig, key)
    if row is None:
        return False
    db.delete(row)
    db.flush()
    return True
