import uuid
from datetime import date, datetime, time
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.dose import DoseStatus
from app.models.medicine import MedStatus, Recurrence


class ScheduleSchema(BaseModel):
    frequency: Recurrence
    interval_n: int = Field(default=1, ge=1)
    days_of_week: Optional[List[int]] = None  # 1 (Monday) to 7 (Sunday)
    days_of_month: Optional[List[int]] = None  # 1 to 31
    times_of_day: List[str] = Field(min_length=1)  # ["08:00", "20:00"]
    start_date: date
    end_date: Optional[date] = None
    anchor_date: Optional[date] = None
    effective_from: date
    effective_to: Optional[date] = None

    model_config = ConfigDict(from_attributes=True)


class MedicineCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    strength: Optional[str] = Field(None, max_length=64)
    form: Optional[str] = Field(default="tablet", max_length=64)
    dose_amount: Decimal = Field(default=Decimal("1.0"), gt=Decimal("0.0"))
    dose_unit: str = Field(default="tablet", max_length=32)
    instructions: Optional[str] = None
    color_tag: Optional[str] = Field(None, max_length=32)
    as_needed: bool = False

    # Schedule parameters (ignored if as_needed=True)
    frequency: Optional[Recurrence] = Recurrence.DAILY
    interval_n: int = Field(default=1, ge=1)
    days_of_week: Optional[List[int]] = None
    days_of_month: Optional[List[int]] = None
    times_of_day: Optional[List[str]] = Field(default=["08:00"])
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    anchor_date: Optional[date] = None

    # Stock
    stock_quantity: Decimal = Field(default=Decimal("0.0"), ge=Decimal("0.0"))
    refill_threshold_days: int = Field(default=5, ge=1)


class MedicineUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    strength: Optional[str] = None
    form: Optional[str] = None
    dose_amount: Optional[Decimal] = Field(None, gt=Decimal("0.0"))
    dose_unit: Optional[str] = None
    instructions: Optional[str] = None
    color_tag: Optional[str] = None
    refill_threshold_days: Optional[int] = Field(None, ge=1)

    # Schedule update takes effect from effective_from (MED-6: default tomorrow)
    effective_from: Optional[date] = None
    frequency: Optional[Recurrence] = None
    interval_n: Optional[int] = Field(None, ge=1)
    days_of_week: Optional[List[int]] = None
    days_of_month: Optional[List[int]] = None
    times_of_day: Optional[List[str]] = None
    end_date: Optional[date] = None


class PauseMedicineRequest(BaseModel):
    paused_until: Optional[date] = None


class MedicineResponse(BaseModel):
    id: uuid.UUID
    elder_id: uuid.UUID
    name: str
    strength: Optional[str] = None
    form: Optional[str] = None
    dose_amount: Decimal
    dose_unit: str
    instructions: Optional[str] = None
    color_tag: Optional[str] = None
    as_needed: bool
    status: MedStatus
    paused_until: Optional[date] = None
    ended_on: Optional[date] = None
    stock_quantity: Decimal
    refill_threshold_days: int
    days_remaining: Optional[int] = None
    active_schedule: Optional[ScheduleSchema] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DoseInstanceResponse(BaseModel):
    id: uuid.UUID
    elder_id: uuid.UUID
    medicine_id: uuid.UUID
    schedule_id: uuid.UUID
    scheduled_date: date
    scheduled_time: time
    scheduled_at: datetime
    medicine_name: str
    dose_label: str
    instructions: Optional[str] = None
    color_tag: Optional[str] = None
    status: DoseStatus
    can_undo: bool = False

    model_config = ConfigDict(from_attributes=True)


class MarkDoseSkippedRequest(BaseModel):
    reason: Optional[str] = Field(None, max_length=255)


class DuplicateCheckResponse(BaseModel):
    is_duplicate: bool
    warning: Optional[str] = None
