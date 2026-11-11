import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    application_id: uuid.UUID | None
    category: str
    title: str
    body: str
    action_url: str | None
    is_read: bool
    read_at: datetime | None
    created_at: datetime


class NotificationsPageOut(BaseModel):
    items: list[NotificationOut]
    total: int
    unread_count: int
    page: int
    page_size: int
