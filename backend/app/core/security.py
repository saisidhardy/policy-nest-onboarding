import hashlib
import hmac
import re
import secrets
from functools import lru_cache

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import get_settings

_hasher = PasswordHasher()

PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 128


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    if not password_hash:
        _burn(password)
        return False
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


@lru_cache
def _dummy_hash() -> str:
    return _hasher.hash(secrets.token_urlsafe(16))


def _burn(password: str) -> None:
    """Spend equivalent hashing time when no account/password exists to blunt user enumeration."""
    try:
        _hasher.verify(_dummy_hash(), password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        pass


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    key = get_settings().secret_key.encode()
    return hmac.new(key, token.encode(), hashlib.sha256).hexdigest()


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


def password_problems(password: str, email: str | None = None, full_name: str | None = None) -> list[str]:
    problems: list[str] = []
    if len(password) < PASSWORD_MIN_LENGTH:
        problems.append(f"Use at least {PASSWORD_MIN_LENGTH} characters.")
    if len(password) > PASSWORD_MAX_LENGTH:
        problems.append(f"Use at most {PASSWORD_MAX_LENGTH} characters.")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        problems.append("Include at least one letter and one number.")
    lowered = password.lower()
    if email:
        local = email.split("@")[0].lower()
        if len(local) >= 4 and local in lowered:
            problems.append("Do not include your email address.")
    if full_name:
        for part in full_name.lower().split():
            if len(part) >= 4 and part in lowered:
                problems.append("Do not include your name.")
                break
    return problems
