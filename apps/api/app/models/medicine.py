import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, List, Optional
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    JSON,
    Numeric,
    SmallInteger,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.core.time import utc_now
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class MedStatus(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    ENDED = "ended"


class Recurrence(str, enum.Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    EVERY_N_DAYS = "every_n_days"
    MONTHLY = "monthly"


class Medicine(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "medicines"

    elder_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("elders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    strength: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    form: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    dose_amount: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("1.0"), nullable=False)
    dose_unit: Mapped[str] = mapped_column(String(32), default="tablet", nullable=False)
    instructions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    color_tag: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    as_needed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[MedStatus] = mapped_column(String(16), default=MedStatus.ACTIVE, nullable=False)
    paused_until: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    ended_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    stock_quantity: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.0"), nullable=False)
    refill_threshold_days: Mapped[int] = mapped_column(SmallInteger, default=5, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    schedules: Mapped[list["MedicineSchedule"]] = relationship(
        "MedicineSchedule", back_populates="medicine", cascade="all, delete-orphan"
    )
    stock_events: Mapped[list["StockEvent"]] = relationship(
        "StockEvent", back_populates="medicine", cascade="all, delete-orphan"
    )


class MedicineSchedule(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "medicine_schedules"

    medicine_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("medicines.id", ondelete="CASCADE"), nullable=False, index=True
    )
    frequency: Mapped[Recurrence] = mapped_column(String(32), nullable=False)
    interval_n: Mapped[int] = mapped_column(SmallInteger, default=1, nullable=False)
    days_of_week: Mapped[Optional[List[int]]] = mapped_column(JSON, nullable=True)  # [1..7]
    days_of_month: Mapped[Optional[List[int]]] = mapped_column(JSON, nullable=True)  # [1..31]
    times_of_day: Mapped[List[str]] = mapped_column(JSON, nullable=False)  # ["08:00", "20:00"]
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    anchor_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    medicine: Mapped["Medicine"] = relationship("Medicine", back_populates="schedules")


class StockEvent(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "stock_events"

    medicine_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("medicines.id", ondelete="CASCADE"), nullable=False, index=True
    )
    delta: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    reason: Mapped[str] = mapped_column(String(32), nullable=False)  # refill, dose_taken, dose_undo, manual_adjust
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    medicine: Mapped["Medicine"] = relationship("Medicine", back_populates="stock_events")
