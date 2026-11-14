import enum
import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.core.time import utc_now
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class ContactRole(str, enum.Enum):
    FAMILY = "family"
    DOCTOR = "doctor"
    NEIGHBOUR = "neighbour"


class Contact(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "contacts"
    __table_args__ = (
        UniqueConstraint("elder_id", "escalation_order", name="uq_contact_elder_escalation_order"),
    )

    elder_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("elders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[ContactRole] = mapped_column(String(32), nullable=False)
    phone_e164: Mapped[str] = mapped_column(String(32), nullable=False)
    whatsapp_e164: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    whatsapp_opt_in: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    preferred_channels: Mapped[List[str]] = mapped_column(JSON, default=lambda: ["sms", "whatsapp"], nullable=False)
    escalation_order: Mapped[int] = mapped_column(Integer, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    elder: Mapped["Elder"] = relationship("Elder", back_populates="contacts")
