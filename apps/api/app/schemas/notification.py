import uuid
from datetime import datetime, time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.sos import DeliveryStatus
from app.models.user import Channel, NotifCategory


class NotificationResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    elder_id: Optional[uuid.UUID] = None
    category: NotifCategory
    template_key: str
    rendered_text: str
    params: Dict[str, Any] = {}
    read_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationListResponse(BaseModel):
    notifications: List[NotificationResponse]
    unread_count: int


class NotificationPreferenceItem(BaseModel):
    category: NotifCategory
    channel: Channel
    enabled: bool


class NotificationPreferencesResponse(BaseModel):
    preferences: List[NotificationPreferenceItem]
    quiet_start: Optional[str] = "22:00"
    quiet_end: Optional[str] = "07:00"


class NotificationPreferencesUpdateRequest(BaseModel):
    preferences: List[NotificationPreferenceItem]
    quiet_start: Optional[str] = Field(None, pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    quiet_end: Optional[str] = Field(None, pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")


class PushSubscribeRequest(BaseModel):
    endpoint: str = Field(min_length=1)
    p256dh: str = Field(min_length=1)
    auth: str = Field(min_length=1)


class WebhookStatusRequest(BaseModel):
    provider_message_id: str
    status: DeliveryStatus
    error_code: Optional[str] = None
