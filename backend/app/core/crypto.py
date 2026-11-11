"""Authenticated encryption and masking helpers for sensitive applicant financial fields."""

import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


@lru_cache
def _fernet_for_secret(secret: str) -> Fernet:
    digest = hashlib.sha256(f"policynest-pii:{secret}".encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _cipher() -> Fernet:
    return _fernet_for_secret(get_settings().secret_key)


def encrypt_sensitive(plaintext: str) -> str:
    """Encrypt a sensitive string value for database persistence."""
    return _cipher().encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_sensitive(ciphertext: str) -> str:
    """Decrypt a previously encrypted field; raises ValueError on invalid token."""
    try:
        return _cipher().decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Unable to decrypt protected field") from exc


def mask_account_number(account_number: str) -> tuple[str, str]:
    """Return (last4, masked_display) for a bank account number."""
    digits = "".join(ch for ch in account_number if ch.isdigit())
    last4 = digits[-4:]
    masked = f"{'X' * max(4, len(digits) - 4)}{last4}"
    return last4, masked
