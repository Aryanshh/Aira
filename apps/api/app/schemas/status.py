import uuid
from datetime import date
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class DaySummaryResponse(BaseModel):
    elder_id: uuid.UUID
    date: date
    total_scheduled: int
    taken_count: int
    missed_count: int
    skipped_count: int
    adherence_pct: int
    state: str  # "all_taken" | "in_progress" | "has_missed" | "no_doses"
    missed_medicine_names: List[str] = []

    model_config = ConfigDict(from_attributes=True)


class WeekSummaryResponse(BaseModel):
    elder_id: uuid.UUID
    week_start: date
    week_end: date
    overall_adherence_pct: int
    total_scheduled: int
    total_taken: int
    total_missed: int
    days: List[DaySummaryResponse]
    missed_highlights: List[str] = []

    model_config = ConfigDict(from_attributes=True)


class MonthSummaryResponse(BaseModel):
    elder_id: uuid.UUID
    year: int
    month: int
    overall_adherence_pct: int
    total_scheduled: int
    total_taken: int
    total_missed: int
    days: List[DaySummaryResponse]

    model_config = ConfigDict(from_attributes=True)


class DayClosureResponse(BaseModel):
    elder_id: uuid.UUID
    closed_date: date
    doses_marked_missed: int
    already_closed: bool

    model_config = ConfigDict(from_attributes=True)
