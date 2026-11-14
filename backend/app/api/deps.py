from dataclasses import dataclass
from typing import Annotated
from urllib.parse import urlparse

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import AppError
from app.core.security import constant_time_equals
from app.models import User, UserSession
from app.models.base import utcnow
from app.rbac.catalog import PERMISSIONS_ALLOWED_UNVERIFIED
from app.rbac.policy import Resource, Subject, evaluate
from app.services import audit
from app.services.auth import find_session, session_is_valid

DB = Annotated[Session, Depends(get_db)]

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
LAST_SEEN_RESOLUTION_SECONDS = 60


@dataclass
class AuthContext:
    user: User
    session: UserSession

    @property
    def permissions(self) -> set[str]:
        return self.user.role.permission_codes

    def subject(self) -> Subject:
        return Subject(
            id=self.user.id,
            role=self.user.role.code,
            permissions=frozenset(self.permissions),
            region=self.user.region,
            clearance_level=self.user.clearance_level,
        )


def _check_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if not origin:
        return
    settings = get_settings()
    origin = origin.rstrip("/")
    if origin in settings.origins:
        return
    host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    if host and urlparse(origin).netloc == host:
        return
    # Auto-allow trusted cloud platform deployments
    origin_netloc = urlparse(origin).netloc.lower()
    if (
        origin_netloc.endswith(".railway.app")
        or origin_netloc.endswith(".up.railway.app")
        or origin_netloc.endswith(".embarko.app")
        or origin_netloc.startswith("localhost")
        or origin_netloc.startswith("127.0.0.1")
    ):
        return
    raise AppError(403, "ORIGIN_REJECTED", "Request origin is not allowed.")


def get_auth(request: Request, db: DB) -> AuthContext:
    settings = get_settings()
    raw = request.cookies.get(settings.session_cookie_name)
    if not raw:
        raise AppError(401, "NOT_AUTHENTICATED", "Sign in to continue.")
    session = find_session(db, raw)
    if session is None or not session_is_valid(session):
        raise AppError(401, "SESSION_EXPIRED", "Your session has expired. Sign in again.")
    user = session.user
    if not user.is_active:
        raise AppError(401, "ACCOUNT_DISABLED", "This account has been disabled.")
    if request.method in UNSAFE_METHODS:
        _check_origin(request)
        header = request.headers.get("x-csrf-token", "")
        if not header or not constant_time_equals(header, session.csrf_token):
            audit.record_independent(
                request,
                "security.csrf_rejected",
                audit.DENIED,
                actor=user,
                details={"path": request.url.path, "method": request.method},
            )
            raise AppError(403, "CSRF_FAILED", "Security token missing or invalid. Refresh the page and try again.")
    now = utcnow()
    if (now - session.last_seen_at).total_seconds() > LAST_SEEN_RESOLUTION_SECONDS:
        session.last_seen_at = now
    request.state.user = user
    return AuthContext(user=user, session=session)


CurrentAuth = Annotated[AuthContext, Depends(get_auth)]


def require_permission(*codes: str):
    def dependency(request: Request, auth: CurrentAuth) -> AuthContext:
        missing = [c for c in codes if c not in auth.permissions]
        if missing:
            audit.record_independent(
                request,
                "access.denied",
                audit.DENIED,
                actor=auth.user,
                details={"missing_permissions": missing, "path": request.url.path, "method": request.method},
            )
            raise AppError(403, "FORBIDDEN", "You do not have permission to perform this action.")
        if (
            get_settings().require_email_verification
            and not auth.user.email_verified
            and any(c not in PERMISSIONS_ALLOWED_UNVERIFIED for c in codes)
        ):
            raise AppError(403, "EMAIL_NOT_VERIFIED", "Verify your email address to continue.")
        return auth

    return dependency


def require_any_permission(*codes: str):
    def dependency(request: Request, auth: CurrentAuth) -> AuthContext:
        matched = [c for c in codes if c in auth.permissions]
        if not matched:
            audit.record_independent(
                request,
                "access.denied",
                audit.DENIED,
                actor=auth.user,
                details={"required_any": list(codes), "path": request.url.path, "method": request.method},
            )
            raise AppError(403, "FORBIDDEN", "You do not have permission to perform this action.")
        if (
            get_settings().require_email_verification
            and not auth.user.email_verified
            and all(c not in PERMISSIONS_ALLOWED_UNVERIFIED for c in matched)
        ):
            raise AppError(403, "EMAIL_NOT_VERIFIED", "Verify your email address to continue.")
        return auth

    return dependency


def enforce_policy(request: Request, auth: AuthContext, permission: str, resource: Resource) -> None:
    decision = evaluate(auth.subject(), permission, resource)
    if not decision.allowed:
        audit.record_independent(
            request,
            "access.denied",
            audit.DENIED,
            actor=auth.user,
            resource_type=resource.type,
            resource_id=resource.id,
            details={"permission": permission, "rule": decision.rule, "reason": decision.reason},
        )
        raise AppError(403, "FORBIDDEN", decision.reason)
