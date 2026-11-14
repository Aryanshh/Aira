import uuid
from datetime import date, datetime, time
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.user import CareRole


class ElderCreateRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    preferred_name: Optional[str] = Field(None, max_length=255)
    date_of_birth: Optional[date] = None
    language: str = Field(default="hi", pattern="^(en|hi)$")
    timezone: str = Field(default="Asia/Kolkata")
    day_close_time: time = Field(default=time(23, 59))
    text_size: int = Field(default=1, ge=0, le=2)

    @field_validator("day_close_time")
    @classmethod
    def validate_day_close_time(cls, v: time) -> time:
        # Spec 8.2: A day-close time earlier than 20:00 is rejected by validation
        if v < time(20, 0):
            raise ValueError("Day close time must not be earlier than 20:00")
        return v


class ElderUpdateRequest(BaseModel):
    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    preferred_name: Optional[str] = Field(None, max_length=255)
    date_of_birth: Optional[date] = None
    language: Optional[str] = Field(None, pattern="^(en|hi)$")
    timezone: Optional[str] = None
    day_close_time: Optional[time] = None
    text_size: Optional[int] = Field(None, ge=0, le=2)

    @field_validator("day_close_time")
    @classmethod
    def validate_day_close_time(cls, v: Optional[time]) -> Optional[time]:
        if v is not None and v < time(20, 0):
            raise ValueError("Day close time must not be earlier than 20:00")
        return v


class ElderResponse(BaseModel):
    id: uuid.UUID
    full_name: str
    preferred_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    language: str
    timezone: str
    day_close_time: time
    text_size: int
    is_owner: bool = False
    can_manage_medicines: bool = False
    role: Optional[CareRole] = None
    archived_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ElderCredentialsResponse(BaseModel):
    elder_id: uuid.UUID
    access_code: str
    pin: str
    qr_token: str
    qr_url: str


class CareTeamMemberResponse(BaseModel):
    user_id: uuid.UUID
    full_name: str
    email: str
    role: CareRole
    is_owner: bool
    can_manage_medicines: bool
    joined_at: datetime


class UpdateTeamMemberRequest(BaseModel):
    role: Optional[CareRole] = None
    can_manage_medicines: Optional[bool] = None


class InviteCreateRequest(BaseModel):
    email: EmailStr
    role: CareRole
    can_manage_medicines: bool = False


class InviteResponse(BaseModel):
    id: uuid.UUID
    email: str
    role: CareRole
    can_manage_medicines: bool
    expires_at: datetime
    invite_url: str


class ElderSessionResponse(BaseModel):
    id: uuid.UUID
    device_label: Optional[str] = None
    created_at: datetime
    last_seen_at: Optional[datetime] = None


class ElderLoginRequest(BaseModel):
    access_code: str = Field(min_length=6, max_length=32)
    pin: str = Field(min_length=4, max_length=4)
    device_label: Optional[str] = None


class ElderQrLoginRequest(BaseModel):
    token: str = Field(min_length=16)
    device_label: Optional[str] = None
