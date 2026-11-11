from fastapi import APIRouter, Depends, Request

from app.api.deps import DB, AuthContext, require_permission
from app.schemas.auth import UpdateProfileRequest, UserOut
from app.services import audit

router = APIRouter(prefix="/account", tags=["account"])


@router.patch("/profile", response_model=UserOut)
def update_profile(
    body: UpdateProfileRequest,
    request: Request,
    db: DB,
    auth: AuthContext = Depends(require_permission("profile:update")),
):
    user = auth.user
    changes: dict[str, dict] = {}
    fields = body.model_fields_set
    if "full_name" in fields and body.full_name and body.full_name != user.full_name:
        changes["full_name"] = {"from": user.full_name, "to": body.full_name}
        user.full_name = body.full_name
    if "mobile" in fields and body.mobile != user.mobile:
        changes["mobile"] = {"changed": True}
        user.mobile = body.mobile
    if (
        "preferred_language" in fields
        and body.preferred_language
        and body.preferred_language != user.preferred_language
    ):
        changes["preferred_language"] = {"from": user.preferred_language, "to": body.preferred_language}
        user.preferred_language = body.preferred_language
    if changes:
        audit.add(
            db,
            request,
            "account.profile_updated",
            actor=user,
            resource_type="user",
            resource_id=str(user.id),
            details={"changes": changes},
        )
    db.flush()
    return UserOut.model_validate(user)
