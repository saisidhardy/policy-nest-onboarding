import uuid

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models import Notification
from app.models.base import utcnow


def create_notification(
    db: Session,
    *,
    user_id: uuid.UUID,
    category: str,
    title: str,
    body: str,
    application_id: uuid.UUID | None = None,
    action_url: str | None = None,
) -> Notification:
    note = Notification(
        id=uuid.uuid4(),
        user_id=user_id,
        application_id=application_id,
        category=category,
        title=title,
        body=body,
        action_url=action_url,
    )
    db.add(note)
    db.flush()
    return note


def list_notifications(
    db: Session,
    user_id: uuid.UUID,
    *,
    unread_only: bool = False,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Notification], int, int]:
    base = select(Notification).where(Notification.user_id == user_id)
    unread_count = (
        db.scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user_id, Notification.is_read.is_(False))
        )
        or 0
    )
    stmt = base.where(Notification.is_read.is_(False)) if unread_only else base
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(
        stmt.order_by(Notification.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return list(items), total, unread_count


def mark_read(db: Session, notification: Notification) -> Notification:
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = utcnow()
        db.flush()
    return notification


def mark_all_read(db: Session, user_id: uuid.UUID) -> int:
    now = utcnow()
    result = db.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.is_read.is_(False))
        .values(is_read=True, read_at=now)
    )
    return result.rowcount or 0
