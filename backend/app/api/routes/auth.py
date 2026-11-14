import uuid
from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response, status
from sqlalchemy import select

from app.api.deps import DB, AuthContext, CurrentAuth, enforce_policy, require_permission
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import (
    PASSWORD_MIN_LENGTH,
    hash_password,
    needs_rehash,
    password_problems,
    verify_password,
)
from app.models import Role, User, UserSession
from app.models.base import utcnow
from app.rbac.catalog import RoleCode
from app.rbac.policy import Resource
from app.schemas.auth import (
    AuthResult,
    ChangePasswordRequest,
    EmailDispatchResult,
    EmailRequest,
    LoginRequest,
    MeOut,
    OtpSendRequest,
    OtpSendResult,
    OtpVerifyRequest,
    RegisterRequest,
    ResetPasswordRequest,
    SessionOut,
    TokenRequest,
    UserOut,
    normalize_mobile,
)
from app.schemas.common import Message
from app.services import audit
from app.services.auth import (
    PURPOSE_EMAIL_VERIFY,
    PURPOSE_INVITE,
    PURPOSE_OTP_LOGIN,
    PURPOSE_PASSWORD_RESET,
    clear_auth_cookies,
    consume_action_token,
    create_session,
    invalidate_action_tokens,
    issue_action_token,
    issue_otp_token,
    latest_action_token,
    live_session_filter,
    peek_action_token,
    revoke_all_sessions,
    set_auth_cookies,
    verify_otp_token,
)
from app.services.email import get_provider, queue_email

router = APIRouter(prefix="/auth", tags=["auth"])


def _weak_password(problems: list[str]) -> AppError:
    return AppError(
        422,
        "WEAK_PASSWORD",
        "Choose a stronger password.",
        [{"field": "password", "message": p} for p in problems],
    )


def _auth_result(user: User, email_delivery: str | None = None) -> AuthResult:
    return AuthResult(
        user=UserOut.model_validate(user),
        permissions=sorted(user.role.permission_codes),
        email_delivery=email_delivery,
    )


def _user_by_email(db: DB, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.lower()))


@router.get("/config", summary="Public authentication configuration")
def auth_config() -> dict:
    s = get_settings()
    return {
        "email_delivery_configured": get_provider().configured,
        "require_email_verification": s.require_email_verification,
        "password_min_length": PASSWORD_MIN_LENGTH,
    }


@router.post("/register", response_model=AuthResult, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, request: Request, response: Response, db: DB, background: BackgroundTasks):
    email = body.email.lower()
    if _user_by_email(db, email):
        raise AppError(409, "EMAIL_ALREADY_REGISTERED", "An account with this email already exists. Sign in instead.")
    problems = password_problems(body.password, email, body.full_name)
    if problems:
        raise _weak_password(problems)
    role = db.scalar(select(Role).where(Role.code == RoleCode.APPLICANT.value))
    assert role is not None, "Roles not seeded; run migrations"
    now = utcnow()
    user = User(
        id=uuid.uuid4(),
        email=email,
        full_name=body.full_name,
        mobile=body.mobile,
        password_hash=hash_password(body.password),
        role=role,
        password_changed_at=now,
        last_login_at=now,
    )
    db.add(user)
    db.flush()
    token = issue_action_token(db, user, PURPOSE_EMAIL_VERIFY, timedelta(hours=get_settings().email_verify_ttl_hours))
    delivery = queue_email(db, background, user, "verify_email", token)
    raw, session = create_session(db, user, request)
    audit.add(
        db,
        request,
        "auth.register",
        actor=user,
        resource_type="user",
        resource_id=str(user.id),
        details={"email_delivery": delivery},
    )
    set_auth_cookies(response, raw, session)
    return _auth_result(user, delivery)


@router.post("/login", response_model=AuthResult)
def login(body: LoginRequest, request: Request, response: Response, db: DB):
    s = get_settings()
    email = body.email.lower()
    user = _user_by_email(db, email)
    now = utcnow()

    if user and user.locked_until and user.locked_until > now:
        verify_password(None, body.password)
        audit.add(db, request, "auth.login", audit.DENIED, actor=user, details={"reason": "locked"})
        db.commit()
        minutes = max(1, int((user.locked_until - now).total_seconds() // 60) + 1)
        raise AppError(
            423, "ACCOUNT_LOCKED", f"Too many failed attempts. Try again in {minutes} minute(s) or reset your password."
        )

    if user is None or not verify_password(user.password_hash, body.password):
        details: dict = {"reason": "invalid_credentials"}
        if user is not None:
            user.failed_login_count += 1
            if user.failed_login_count >= s.login_max_failures:
                user.locked_until = now + timedelta(minutes=s.login_lockout_minutes)
                user.failed_login_count = 0
                details["locked"] = True
                audit.add(
                    db,
                    request,
                    "auth.account_locked",
                    audit.SUCCESS,
                    actor=user,
                    resource_type="user",
                    resource_id=str(user.id),
                )
        audit.add(db, request, "auth.login", audit.FAILURE, actor=user, actor_email=email, details=details)
        db.commit()
        raise AppError(401, "INVALID_CREDENTIALS", "Incorrect email or password.")

    if not user.is_active:
        audit.add(db, request, "auth.login", audit.DENIED, actor=user, details={"reason": "disabled"})
        db.commit()
        raise AppError(403, "ACCOUNT_DISABLED", "This account has been disabled. Contact your administrator.")

    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    if user.password_hash and needs_rehash(user.password_hash):
        user.password_hash = hash_password(body.password)
    raw, session = create_session(db, user, request)
    audit.add(db, request, "auth.login", actor=user, details={"session_id": str(session.id)})
    set_auth_cookies(response, raw, session)
    return _auth_result(user)


def _normalize_identifier(identifier: str) -> tuple[str, str]:
    raw = identifier.strip()
    if "@" in raw:
        return raw.lower(), "EMAIL"
    clean_mobile = normalize_mobile(raw)
    if clean_mobile:
        return clean_mobile, "MOBILE"
    raise AppError(422, "INVALID_IDENTIFIER", "Enter a valid email address or 10-digit Indian mobile number.")


def _mask_destination(val: str, kind: str) -> str:
    if kind == "EMAIL":
        parts = val.split("@")
        name = parts[0]
        domain = parts[1] if len(parts) > 1 else ""
        masked_name = name[0] + "***" + (name[-1] if len(name) > 1 else "")
        return f"{masked_name}@{domain}"
    return f"+91 {val[:2]}***{val[-2:]}" if len(val) >= 4 else "+91 **********"


@router.post("/otp/send", response_model=OtpSendResult)
def send_otp(body: OtpSendRequest, db: DB, background: BackgroundTasks):
    val, kind = _normalize_identifier(body.identifier)
    user = None
    if kind == "EMAIL":
        user = _user_by_email(db, val)
    else:
        user = db.scalar(select(User).where(User.mobile == val))

    # Auto-provision APPLICANT candidate if account does not exist
    if user is None:
        applicant_role = db.scalar(select(Role).where(Role.code == RoleCode.APPLICANT.value))
        assert applicant_role is not None, "Roles not seeded"
        now = utcnow()
        user_email = val if kind == "EMAIL" else f"posp_{val}@policynest.auto"
        user_mobile = val if kind == "MOBILE" else None
        user = User(
            id=uuid.uuid4(),
            email=user_email,
            mobile=user_mobile,
            full_name="POSP Applicant",
            role=applicant_role,
            is_active=True,
            password_hash=None,
            password_changed_at=now,
            last_login_at=now,
        )
        db.add(user)
        db.flush()

    if not user.is_active:
        raise AppError(403, "ACCOUNT_DISABLED", "This account has been disabled. Contact support.")

    # Check cooldown (60 seconds)
    recent = latest_action_token(db, user, PURPOSE_OTP_LOGIN)
    if recent and recent.created_at and (utcnow() - recent.created_at).total_seconds() < 60:
        remain = 60 - int((utcnow() - recent.created_at).total_seconds())
        raise AppError(429, "RATE_LIMITED", f"Please wait {remain} seconds before requesting a new code.")

    otp = issue_otp_token(db, user, ttl_minutes=10)

    if kind == "EMAIL" or (user.email and not user.email.endswith(".auto")):
        queue_email(db, background, user, "otp_login", otp)

    masked = _mask_destination(val, kind)
    return OtpSendResult(
        success=True,
        delivery_channel=kind,
        destination_masked=masked,
        message=f"A 6-digit verification code has been dispatched to {masked}.",
        cooldown_seconds=60,
        debug_code=None,
    )


@router.post("/otp/verify", response_model=AuthResult)
def verify_otp(body: OtpVerifyRequest, request: Request, response: Response, db: DB):
    val, kind = _normalize_identifier(body.identifier)
    user = None
    if kind == "EMAIL":
        user = _user_by_email(db, val)
    else:
        user = db.scalar(select(User).where(User.mobile == val))

    if user is None:
        raise AppError(401, "INVALID_CREDENTIALS", "Account not found for this identifier. Request a code first.")

    now = utcnow()
    if user.locked_until and user.locked_until > now:
        minutes = max(1, int((user.locked_until - now).total_seconds() // 60) + 1)
        raise AppError(423, "ACCOUNT_LOCKED", f"Too many failed attempts. Try again in {minutes} minute(s).")

    if not verify_otp_token(db, user, body.code):
        user.failed_login_count += 1
        s = get_settings()
        if user.failed_login_count >= s.login_max_failures:
            user.locked_until = now + timedelta(minutes=s.login_lockout_minutes)
            user.failed_login_count = 0
        audit.add(db, request, "auth.otp_verify", audit.FAILURE, actor=user, details={"reason": "invalid_code"})
        db.commit()
        raise AppError(401, "INVALID_CODE", "Invalid or expired verification code.")

    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    if not user.email_verified_at and kind == "EMAIL":
        user.email_verified_at = now

    raw, session = create_session(db, user, request)
    audit.add(db, request, "auth.otp_login", actor=user, details={"session_id": str(session.id), "kind": kind})
    set_auth_cookies(response, raw, session)
    return _auth_result(user)


@router.post("/logout", response_model=Message)
def logout(request: Request, response: Response, auth: CurrentAuth, db: DB):
    auth.session.revoked_at = utcnow()
    audit.add(db, request, "auth.logout", actor=auth.user, details={"session_id": str(auth.session.id)})
    clear_auth_cookies(response)
    return Message(message="Signed out.")


@router.get("/me", response_model=MeOut)
def me(auth: CurrentAuth):
    return MeOut(
        user=UserOut.model_validate(auth.user),
        permissions=sorted(auth.permissions),
        session_expires_at=auth.session.expires_at,
        email_delivery_configured=get_provider().configured,
    )


@router.post("/verify-email", response_model=Message)
def verify_email(body: TokenRequest, request: Request, db: DB):
    token = consume_action_token(db, body.token, {PURPOSE_EMAIL_VERIFY})
    user = token.user
    if user.email_verified_at is None:
        user.email_verified_at = utcnow()
    audit.add(db, request, "auth.email_verified", actor=user, resource_type="user", resource_id=str(user.id))
    return Message(message="Email verified.")


@router.post("/resend-verification", response_model=EmailDispatchResult)
def resend_verification(
    request: Request,
    db: DB,
    background: BackgroundTasks,
    auth: AuthContext = Depends(require_permission("profile:read")),
):
    s = get_settings()
    user = auth.user
    if user.email_verified:
        raise AppError(400, "ALREADY_VERIFIED", "Your email is already verified.")
    last = latest_action_token(db, user, PURPOSE_EMAIL_VERIFY)
    if last and (utcnow() - last.created_at).total_seconds() < s.email_resend_cooldown_seconds:
        raise AppError(429, "RATE_LIMITED", "Please wait a minute before requesting another email.")
    token = issue_action_token(db, user, PURPOSE_EMAIL_VERIFY, timedelta(hours=s.email_verify_ttl_hours))
    delivery = queue_email(db, background, user, "verify_email", token)
    audit.add(db, request, "auth.verification_resent", actor=user, details={"email_delivery": delivery})
    return EmailDispatchResult(message="Verification email requested.", email_delivery=delivery)


@router.post("/forgot-password", response_model=Message, status_code=status.HTTP_202_ACCEPTED)
def forgot_password(body: EmailRequest, request: Request, db: DB, background: BackgroundTasks):
    s = get_settings()
    user = _user_by_email(db, body.email)
    generic = Message(message="If an account exists for that email, a reset link has been sent.")
    if user is None or not user.is_active:
        audit.add(
            db,
            request,
            "auth.password_reset_requested",
            audit.FAILURE,
            actor_email=body.email.lower(),
            details={"reason": "unknown_or_inactive"},
        )
        return generic
    last = latest_action_token(db, user, PURPOSE_PASSWORD_RESET)
    if last and (utcnow() - last.created_at).total_seconds() < s.email_resend_cooldown_seconds:
        return generic
    token = issue_action_token(db, user, PURPOSE_PASSWORD_RESET, timedelta(minutes=s.password_reset_ttl_minutes))
    delivery = queue_email(db, background, user, "password_reset", token)
    audit.add(db, request, "auth.password_reset_requested", actor=user, details={"email_delivery": delivery})
    return generic


@router.post("/check-token", summary="Check whether a reset/invite/verify link is still usable")
def check_token(body: TokenRequest, db: DB) -> dict:
    token = peek_action_token(db, body.token, {PURPOSE_PASSWORD_RESET, PURPOSE_INVITE, PURPOSE_EMAIL_VERIFY})
    return {"valid": True, "purpose": token.purpose, "email": token.user.email, "full_name": token.user.full_name}


@router.post("/reset-password", response_model=Message)
def reset_password(body: ResetPasswordRequest, request: Request, db: DB):
    token = peek_action_token(db, body.token, {PURPOSE_PASSWORD_RESET, PURPOSE_INVITE})
    user = token.user
    problems = password_problems(body.password, user.email, user.full_name)
    if problems:
        raise _weak_password(problems)
    # Serialise resets per user so claiming one link and invalidating the rest cannot deadlock.
    db.execute(select(User.id).where(User.id == user.id).with_for_update())
    consume_action_token(db, body.token, {PURPOSE_PASSWORD_RESET, PURPOSE_INVITE})
    invalidate_action_tokens(db, user.id, {PURPOSE_PASSWORD_RESET, PURPOSE_INVITE})
    now = utcnow()
    user.password_hash = hash_password(body.password)
    user.password_changed_at = now
    user.failed_login_count = 0
    user.locked_until = None
    if user.email_verified_at is None:
        user.email_verified_at = now
    revoked = revoke_all_sessions(db, user.id)
    action = "auth.invite_accepted" if token.purpose == PURPOSE_INVITE else "auth.password_reset"
    audit.add(
        db,
        request,
        action,
        actor=user,
        resource_type="user",
        resource_id=str(user.id),
        details={"sessions_revoked": revoked},
    )
    return Message(message="Password updated. You can now sign in.")


@router.post("/change-password", response_model=Message)
def change_password(
    body: ChangePasswordRequest,
    request: Request,
    db: DB,
    auth: AuthContext = Depends(require_permission("profile:update")),
):
    user = auth.user
    if not verify_password(user.password_hash, body.current_password):
        audit.add(db, request, "auth.password_change", audit.FAILURE, actor=user, details={"reason": "wrong_current"})
        db.commit()
        raise AppError(400, "INVALID_CURRENT_PASSWORD", "Your current password is incorrect.")
    problems = password_problems(body.new_password, user.email, user.full_name)
    if problems:
        raise _weak_password(problems)
    if verify_password(user.password_hash, body.new_password):
        raise _weak_password(["Choose a password different from your current one."])
    user.password_hash = hash_password(body.new_password)
    user.password_changed_at = utcnow()
    revoked = revoke_all_sessions(db, user.id, except_session_id=auth.session.id)
    audit.add(db, request, "auth.password_change", actor=user, details={"other_sessions_revoked": revoked})
    return Message(message="Password changed. Other sessions were signed out.")


@router.get("/sessions", response_model=list[SessionOut])
def list_sessions(db: DB, auth: AuthContext = Depends(require_permission("profile:read"))):
    now = utcnow()
    rows = db.scalars(
        select(UserSession)
        .where(UserSession.user_id == auth.user.id, *live_session_filter(now))
        .order_by(UserSession.last_seen_at.desc())
    ).all()
    out = []
    for row in rows:
        item = SessionOut.model_validate(row)
        item.current = row.id == auth.session.id
        out.append(item)
    return out


@router.delete("/sessions/{session_id}", response_model=Message)
def revoke_session(
    session_id: uuid.UUID,
    request: Request,
    db: DB,
    auth: AuthContext = Depends(require_permission("profile:update")),
):
    target = db.get(UserSession, session_id)
    if target is None or target.revoked_at is not None:
        raise AppError(404, "NOT_FOUND", "Session not found.")
    enforce_policy(
        request, auth, "profile:update", Resource(type="session", id=str(target.id), owner_id=target.user_id)
    )
    target.revoked_at = utcnow()
    audit.add(db, request, "auth.session_revoked", actor=auth.user, resource_type="session", resource_id=str(target.id))
    return Message(message="Session signed out.")
