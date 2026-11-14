import enum
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.time import utc_now
from app.models.base import UUIDPrimaryKeyMixin


class SosStatus(str, enum.Enum):
    ACTIVE = "active"
    HANDLED = "handled"
    FAILED = "failed"


class SosSource(str, enum.Enum):
    DEVICE = "device"
    WEB = "web"


class EscalationState(str, enum.Enum):
    IN_PROGRESS = "in_progress"
    EXHAUSTED = "exhausted"
    ACKNOWLEDGED = "acknowledged"


class DeliveryStatus(str, enum.Enum):
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"


class SosEvent(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "sos_events"
    __table_args__ = (
        UniqueConstraint("elder_id", "client_event_id", name="uq_sos_elder_client_event_id"),
        Index("ix_sos_events_elder_triggered", "elder_id", "triggered_at"),
    )

    elder_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("elders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source: Mapped[SosSource] = mapped_column(String(16), nullable=False)
    device_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("devices.id", ondelete="SET NULL"), nullable=True
    )
    client_event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[SosStatus] = mapped_column(String(16), default=SosStatus.ACTIVE, nullable=False, index=True)
    escalation_state: Mapped[EscalationState] = mapped_column(
        String(32), default=EscalationState.IN_PROGRESS, nullable=False
    )
    press_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    handled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    handled_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class SosAttempt(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "sos_attempts"

    sos_event_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("sos_events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    contact_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("contacts.id", ondelete="CASCADE"), nullable=True
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    channel: Mapped[str] = mapped_column(String(16), nullable=False)  # in_app, push, email, sms, whatsapp
    round: Mapped[int] = mapped_column(SmallInteger, default=1, nullable=False)
    status: Mapped[DeliveryStatus] = mapped_column(String(16), default=DeliveryStatus.QUEUED, nullable=False)
    provider_message_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    next_attempt_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class SosAcknowledgement(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "sos_acknowledgements"

    sos_event_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("sos_events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    contact_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("contacts.id", ondelete="CASCADE"), nullable=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
