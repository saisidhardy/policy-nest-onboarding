import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.rbac.catalog import REGIONS, RoleCode
from app.schemas.auth import UserOut, normalize_name

RegionLiteral = Literal["NORTH", "SOUTH", "EAST", "WEST", "ALL"]


class AdminUserOut(UserOut):
    locked_until: datetime | None
    failed_login_count: int
    invitation_pending: bool


class CreateUserRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(max_length=200)
    role: RoleCode
    region: RegionLiteral | None = None
    clearance_level: int = Field(default=1, ge=1, le=3)

    _name = field_validator("full_name")(normalize_name)


class UpdateUserRequest(BaseModel):
    role: RoleCode | None = None
    is_active: bool | None = None
    region: RegionLiteral | None = None
    clearance_level: int | None = Field(default=None, ge=1, le=3)
    clear_region: bool = False


class PermissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    code: str
    category: str
    description: str


class RoleDetailOut(BaseModel):
    code: str
    name: str
    description: str
    is_staff: bool
    user_count: int
    permissions: list[str]


class RolesMatrixOut(BaseModel):
    roles: list[RoleDetailOut]
    permissions: list[PermissionOut]
    regions: list[str] = REGIONS


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    occurred_at: datetime
    actor_user_id: uuid.UUID | None
    actor_email: str | None
    actor_role: str | None
    action: str
    outcome: str
    resource_type: str | None
    resource_id: str | None
    ip_address: str | None
    request_id: str | None
    details: dict[str, Any]


class IntegrationStatus(BaseModel):
    key: str
    name: str
    status: Literal["CONFIGURED", "NOT_CONFIGURED", "DEGRADED"]
    mode: Literal["LIVE", "LOCAL_DEVELOPMENT", "SANDBOX", "NONE"]
    detail: str


class SystemHealthOut(BaseModel):
    status: str
    app_env: str
    version: str
    database: dict[str, Any]
    integrations: list[IntegrationStatus]
    email_deliveries_last_24h: dict[str, int]


class AdminStatsOut(BaseModel):
    users_by_role: dict[str, int]
    active_users: int
    inactive_users: int
    unverified_users: int
    pending_invitations: int
    active_sessions: int
    registrations_last_7_days: int
    failed_logins_last_24h: int
    recent_audit: list[AuditLogOut]
