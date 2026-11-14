from datetime import datetime, timedelta

from fastapi import Request, Response
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.request_context import client_ip, user_agent
from app.core.security import generate_token, hash_token
from app.models import User, UserActionToken, UserSession
from app.models.base import utcnow

PURPOSE_EMAIL_VERIFY = "EMAIL_VERIFY"
PURPOSE_PASSWORD_RESET = "PASSWORD_RESET"
PURPOSE_INVITE = "INVITE"
PURPOSE_OTP_LOGIN = "OTP_LOGIN"


def create_session(db: Session, user: User, request: Request) -> tuple[str, UserSession]:
    s = get_settings()
    raw = generate_token()
    now = utcnow()
    session = UserSession(
        user_id=user.id,
        token_hash=hash_token(raw),
        csrf_token=generate_token(),
        last_seen_at=now,
        expires_at=now + timedelta(hours=s.session_absolute_hours),
        ip_address=client_ip(request),
        user_agent=user_agent(request),
    )
    db.add(session)
    db.flush()
    return raw, session


def set_auth_cookies(response: Response, raw_token: str, session: UserSession) -> None:
    s = get_settings()
    max_age = int((session.expires_at - utcnow()).total_seconds())
    response.set_cookie(
        s.session_cookie_name,
        raw_token,
        max_age=max_age,
        httponly=True,
        secure=s.secure_cookies,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        s.csrf_cookie_name,
        session.csrf_token,
        max_age=max_age,
        httponly=False,
        secure=s.secure_cookies,
        samesite="lax",
        path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    s = get_settings()
    response.delete_cookie(s.session_cookie_name, path="/")
    response.delete_cookie(s.csrf_cookie_name, path="/")


def session_is_valid(session: UserSession, now: datetime | None = None) -> bool:
    now = now or utcnow()
    idle_limit = timedelta(minutes=get_settings().session_idle_minutes)
    return session.revoked_at is None and session.expires_at > now and now - session.last_seen_at <= idle_limit


def live_session_filter(now: datetime):
    idle_limit = timedelta(minutes=get_settings().session_idle_minutes)
    return (
        UserSession.revoked_at.is_(None),
        UserSession.expires_at > now,
        UserSession.last_seen_at >= now - idle_limit,
    )


def find_session(db: Session, raw_token: str) -> UserSession | None:
    return db.scalar(select(UserSession).where(UserSession.token_hash == hash_token(raw_token)))


def revoke_all_sessions(db: Session, user_id, except_session_id=None) -> int:
    # Lock order is always user row, then session rows, so concurrent password/admin changes cannot deadlock.
    db.execute(select(User.id).where(User.id == user_id).with_for_update())
    stmt = (
        update(UserSession)
        .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )
    if except_session_id is not None:
        stmt = stmt.where(UserSession.id != except_session_id)
    return db.execute(stmt).rowcount or 0


def issue_action_token(db: Session, user: User, purpose: str, ttl: timedelta) -> str:
    db.execute(
        update(UserActionToken)
        .where(
            UserActionToken.user_id == user.id,
            UserActionToken.purpose == purpose,
            UserActionToken.used_at.is_(None),
        )
        .values(used_at=utcnow())
    )
    raw = generate_token()
    db.add(UserActionToken(user_id=user.id, purpose=purpose, token_hash=hash_token(raw), expires_at=utcnow() + ttl))
    return raw


def issue_otp_token(db: Session, user: User, ttl_minutes: int = 10) -> str:
    import secrets

    db.execute(
        update(UserActionToken)
        .where(
            UserActionToken.user_id == user.id,
            UserActionToken.purpose == PURPOSE_OTP_LOGIN,
            UserActionToken.used_at.is_(None),
        )
        .values(used_at=utcnow())
    )
    otp = f"{secrets.randbelow(900000) + 100000}"
    db.add(
        UserActionToken(
            user_id=user.id,
            purpose=PURPOSE_OTP_LOGIN,
            token_hash=hash_token(f"{user.id}:{otp}"),
            expires_at=utcnow() + timedelta(minutes=ttl_minutes),
        )
    )
    return otp


def verify_otp_token(db: Session, user: User, otp: str) -> bool:
    token_hash = hash_token(f"{user.id}:{otp.strip()}")
    token = db.scalar(
        select(UserActionToken).where(
            UserActionToken.user_id == user.id,
            UserActionToken.purpose == PURPOSE_OTP_LOGIN,
            UserActionToken.token_hash == token_hash,
            UserActionToken.used_at.is_(None),
            UserActionToken.expires_at > utcnow(),
        )
    )
    if token is None:
        return False
    token.used_at = utcnow()
    return True


def latest_action_token(db: Session, user: User, purpose: str) -> UserActionToken | None:
    return db.scalar(
        select(UserActionToken)
        .where(UserActionToken.user_id == user.id, UserActionToken.purpose == purpose)
        .order_by(UserActionToken.created_at.desc())
        .limit(1)
    )


def peek_action_token(db: Session, raw: str, purposes: set[str]) -> UserActionToken:
    token = db.scalar(select(UserActionToken).where(UserActionToken.token_hash == hash_token(raw)))
    if token is None or token.purpose not in purposes:
        raise AppError(400, "TOKEN_INVALID", "This link is invalid.")
    if token.used_at is not None:
        raise AppError(400, "TOKEN_USED", "This link has already been used.")
    if token.expires_at <= utcnow():
        raise AppError(400, "TOKEN_EXPIRED", "This link has expired. Request a new one.")
    if not token.user.is_active:
        raise AppError(400, "TOKEN_INVALID", "This link is invalid.")
    return token


def consume_action_token(db: Session, raw: str, purposes: set[str]) -> UserActionToken:
    token = peek_action_token(db, raw, purposes)
    claimed = db.execute(
        update(UserActionToken)
        .where(UserActionToken.id == token.id, UserActionToken.used_at.is_(None))
        .values(used_at=utcnow())
        .execution_options(synchronize_session=False)
    ).rowcount
    if claimed != 1:
        raise AppError(400, "TOKEN_USED", "This link has already been used.")
    db.expire(token, ["used_at"])
    return token


def invalidate_action_tokens(db: Session, user_id, purposes: set[str]) -> None:
    db.execute(
        update(UserActionToken)
        .where(
            UserActionToken.user_id == user_id,
            UserActionToken.purpose.in_(purposes),
            UserActionToken.used_at.is_(None),
        )
        .values(used_at=utcnow())
        .execution_options(synchronize_session=False)
    )
