import uuid

from fastapi import APIRouter, Depends, Query, Request

from app.api.deps import DB, AuthContext, enforce_policy, require_permission
from app.core.errors import AppError
from app.models import Notification
from app.rbac.policy import Resource
from app.schemas.common import Message
from app.schemas.notification import NotificationOut, NotificationsPageOut
from app.services import notifications as notif_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationsPageOut)
def list_my_notifications(
    db: DB,
    auth: AuthContext = Depends(require_permission("profile:read")),
    unread_only: bool = False,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    items, total, unread_count = notif_service.list_notifications(
        db,
        auth.user.id,
        unread_only=unread_only,
        page=page,
        page_size=page_size,
    )
    return NotificationsPageOut(
        items=[NotificationOut.model_validate(n) for n in items],
        total=total,
        unread_count=unread_count,
        page=page,
        page_size=page_size,
    )


@router.post("/{notification_id}/read", response_model=NotificationOut)
def mark_notification_read(
    notification_id: uuid.UUID,
    request: Request,
    db: DB,
    auth: AuthContext = Depends(require_permission("profile:update")),
):
    note = db.get(Notification, notification_id)
    if note is None:
        raise AppError(404, "NOT_FOUND", "Notification not found.")
    enforce_policy(
        request,
        auth,
        "profile:update",
        Resource(type="notification", id=str(note.id), owner_id=note.user_id),
    )
    return NotificationOut.model_validate(notif_service.mark_read(db, note))


@router.post("/read-all", response_model=Message)
def mark_all_notifications_read(
    db: DB,
    auth: AuthContext = Depends(require_permission("profile:update")),
):
    count = notif_service.mark_all_read(db, auth.user.id)
    return Message(message=f"Marked {count} notification(s) as read.")
