import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

MOBILE_RE = re.compile(r"^[6-9]\d{9}$")
LanguageCode = Literal["EN", "HI"]


def normalize_mobile(value: str | None) -> str | None:
    if value is None:
        return None
    digits = re.sub(r"[\s\-()]", "", value)
    if digits.startswith("+91"):
        digits = digits[3:]
    elif digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    if digits == "":
        return None
    if not MOBILE_RE.match(digits):
        raise ValueError("Enter a valid 10-digit Indian mobile number.")
    return digits


def normalize_name(value: str) -> str:
    cleaned = " ".join(value.split())
    if len(cleaned) < 2:
        raise ValueError("Enter your full name.")
    if not re.fullmatch(r"[A-Za-z][A-Za-z .'\-]*", cleaned):
        raise ValueError("Use letters, spaces, dots, apostrophes or hyphens only.")
    return cleaned


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)
    full_name: str = Field(max_length=200)
    mobile: str | None = None
    accept_terms: bool

    _name = field_validator("full_name")(normalize_name)
    _mobile = field_validator("mobile")(normalize_mobile)

    @field_validator("accept_terms")
    @classmethod
    def _terms(cls, v: bool) -> bool:
        if not v:
            raise ValueError("You must accept the terms and privacy notice.")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class TokenRequest(BaseModel):
    token: str = Field(min_length=10, max_length=200)


class EmailRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    password: str = Field(min_length=1, max_length=256)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)


class UpdateProfileRequest(BaseModel):
    full_name: str | None = Field(default=None, max_length=200)
    mobile: str | None = None
    preferred_language: LanguageCode | None = None

    @field_validator("full_name")
    @classmethod
    def _name(cls, v: str | None) -> str | None:
        return normalize_name(v) if v is not None else None

    _mobile = field_validator("mobile")(normalize_mobile)


class RoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    code: str
    name: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: str
    full_name: str
    mobile: str | None
    preferred_language: str
    role: RoleOut
    is_active: bool
    email_verified: bool
    region: str | None
    clearance_level: int
    last_login_at: datetime | None
    created_at: datetime


class MeOut(BaseModel):
    user: UserOut
    permissions: list[str]
    session_expires_at: datetime
    email_delivery_configured: bool


class AuthResult(BaseModel):
    user: UserOut
    permissions: list[str]
    email_delivery: str | None = None


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    ip_address: str | None
    user_agent: str | None
    current: bool = False


class EmailDispatchResult(BaseModel):
    message: str
    email_delivery: str
