import uuid
from datetime import date, datetime, time
from typing import Optional
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Time,
    UniqueConstraint,
    Uuid,
    LargeBinary,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.core.time import utc_now
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.user import CareRole


class Elder(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "elders"

    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    preferred_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    language: Mapped[str] = mapped_column(String(8), default="hi", nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata", nullable=False)
    day_close_time: Mapped[time] = mapped_column(Time, default=time(23, 59), nullable=False)
    text_size: Mapped[int] = mapped_column(SmallInteger, default=1, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    care_links: Mapped[list["CareLink"]] = relationship(
        "CareLink", back_populates="elder", cascade="all, delete-orphan"
    )
    credentials: Mapped[Optional["ElderCredentials"]] = relationship(
        "ElderCredentials", back_populates="elder", uselist=False, cascade="all, delete-orphan"
    )
    sessions: Mapped[list["ElderSession"]] = relationship(
        "ElderSession", back_populates="elder", cascade="all, delete-orphan"
    )
    contacts: Mapped[list["Contact"]] = relationship(
        "Contact", back_populates="elder", cascade="all, delete-orphan"
    )


class CareLink(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "care_links"
    __table_args__ = (UniqueConstraint("elder_id", "user_id", name="uq_care_link_elder_user"),)

    elder_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("elders.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[CareRole] = mapped_column(String(16), nullable=False)
    is_owner: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_manage_medicines: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    elder: Mapped["Elder"] = relationship("Elder", back_populates="care_links")
    user: Mapped["User"] = relationship("User", back_populates="care_links")


class Invite(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "invites"

    elder_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("elders.id", ondelete="CASCADE"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[CareRole] = mapped_column(String(16), nullable=False)
    can_manage_medicines: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    invited_by: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class ElderCredentials(Base):
    __tablename__ = "elder_credentials"

    elder_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("elders.id", ondelete="CASCADE"), primary_key=True
    )
    access_code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    pin_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    qr_token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    rotated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    elder: Mapped["Elder"] = relationship("Elder", back_populates="credentials")


class ElderSession(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "elder_sessions"

    elder_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("elders.id", ondelete="CASCADE"), nullable=False
    )
    device_label: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    refresh_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    elder: Mapped["Elder"] = relationship("Elder", back_populates="sessions")


class Device(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "devices"

    elder_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("elders.id", ondelete="CASCADE"), nullable=False
    )
    label: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    secret_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
