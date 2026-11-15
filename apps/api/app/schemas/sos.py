import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.contact import ContactRole
from app.models.sos import EscalationState, SosSource, SosStatus


class ContactCreateRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    role: ContactRole = ContactRole.FAMILY
    phone_e164: str = Field(pattern=r"^\+[1-9]\d{1,14}$")
    whatsapp_e164: Optional[str] = Field(None, pattern=r"^\+[1-9]\d{1,14}$")
    email: Optional[EmailStr] = None
    whatsapp_opt_in: bool = True
    preferred_channels: List[str] = ["sms", "whatsapp"]
    escalation_order: Optional[int] = Field(None, ge=1)


class ContactUpdateRequest(BaseModel):
    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    role: Optional[ContactRole] = None
    phone_e164: Optional[str] = Field(None, pattern=r"^\+[1-9]\d{1,14}$")
    whatsapp_e164: Optional[str] = Field(None, pattern=r"^\+[1-9]\d{1,14}$")
    email: Optional[EmailStr] = None
    whatsapp_opt_in: Optional[bool] = None
    preferred_channels: Optional[List[str]] = None
    escalation_order: Optional[int] = Field(None, ge=1)
    active: Optional[bool] = None


class ContactResponse(BaseModel):
    id: uuid.UUID
    elder_id: uuid.UUID
    full_name: str
    role: ContactRole
    phone_e164: str
    whatsapp_e164: Optional[str] = None
    email: Optional[str] = None
    whatsapp_opt_in: bool
    preferred_channels: List[str]
    escalation_order: int
    active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ContactsReorderRequest(BaseModel):
    contact_ids: List[uuid.UUID]


class SosTriggerRequest(BaseModel):
    elder_id: uuid.UUID
    source: SosSource = SosSource.WEB
    client_event_id: Optional[str] = None


class SosResolveRequest(BaseModel):
    note: Optional[str] = Field(None, max_length=500)


class SosAttemptResponse(BaseModel):
    id: uuid.UUID
    contact_name: Optional[str] = None
    channel: str
    round: int
    status: str
    sent_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class SosEventResponse(BaseModel):
    id: uuid.UUID
    elder_id: uuid.UUID
    source: SosSource
    client_event_id: str
    status: SosStatus
    escalation_state: EscalationState
    press_count: int
    triggered_at: datetime
    handled_at: Optional[datetime] = None
    handled_by: Optional[uuid.UUID] = None
    attempts: List[SosAttemptResponse] = []

    model_config = ConfigDict(from_attributes=True)
