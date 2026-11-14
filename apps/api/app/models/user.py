import enum
import uuid
from datetime import datetime, time
from typing import Optional
from sqlalchemy import Boolean, DateTime, String, Time, Uuid, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.core.time import utc_now
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class CareRole(str, enum.Enum):
    FAMILY = "family"
    CAREGIVER = "caregiver"


class Channel(str, enum.Enum):
    IN_APP = "in_app"
    PUSH = "push"
    EMAIL = "email"
    SMS = "sms"
    WHATSAPP = "whatsapp"


class NotifCategory(str, enum.Enum):
    SOS = "sos"
    MISSED = "missed"
    REFILL = "refill"
    SYSTEM = "system"


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone_e164: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    preferred_language: Mapped[str] = mapped_column(String(8), default="en", nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata", nullable=False)
    quiet_start: Mapped[Optional[time]] = mapped_column(Time, default=time(22, 0), nullable=True)
    quiet_end: Mapped[Optional[time]] = mapped_column(Time, default=time(7, 0), nullable=True)
    email_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    refresh_tokens: Mapped[list["UserRefreshToken"]] = relationship(
        "UserRefreshToken", back_populates="user", cascade="all, delete-orphan"
    )
    care_links: Mapped[list["CareLink"]] = relationship(
        "CareLink", back_populates="user", cascade="all, delete-orphan"
    )


class UserRefreshToken(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "user_refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    family_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="refresh_tokens")
