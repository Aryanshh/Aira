import enum
import uuid
from datetime import date, datetime, time
from typing import Optional
from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Time,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.time import utc_now
from app.models.base import UUIDPrimaryKeyMixin


class DoseStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    TAKEN = "taken"
    MISSED = "missed"
    SKIPPED = "skipped"


class DoseInstance(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "dose_instances"
    __table_args__ = (
        UniqueConstraint("medicine_id", "scheduled_date", "scheduled_time", name="uq_dose_med_date_time"),
        Index("ix_dose_instances_elder_date_status", "elder_id", "scheduled_date", "status"),
    )

    elder_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("elders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    medicine_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("medicines.id", ondelete="CASCADE"), nullable=False, index=True
    )
    schedule_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("medicine_schedules.id", ondelete="CASCADE"), nullable=False
    )
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    scheduled_time: Mapped[time] = mapped_column(Time, nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    medicine_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    dose_label_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[DoseStatus] = mapped_column(String(16), default=DoseStatus.SCHEDULED, nullable=False, index=True)
    resolved_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)  # Privacy by design: date only
    resolved_by_actor: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)  # elder | user:<id> | system
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class DayClosure(Base):
    __tablename__ = "day_closures"

    elder_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("elders.id", ondelete="CASCADE"), primary_key=True
    )
    closed_date: Mapped[date] = mapped_column(Date, primary_key=True)
    closed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
