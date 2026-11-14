import uuid
from datetime import date, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.models.user import User
from app.routers.deps import get_current_user
from app.schemas.status import (
    DayClosureResponse,
    DaySummaryResponse,
    MonthSummaryResponse,
    WeekSummaryResponse,
)
from app.services.status_service import StatusService

router = APIRouter(prefix="/api/v1/elders", tags=["Status & Summaries"])


@router.get("/{elder_id}/status/day", response_model=DaySummaryResponse)
async def get_day_status(
    elder_id: uuid.UUID,
    target_date: Optional[date] = Query(None, alias="date"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DaySummaryResponse:
    """Get day status summary (STA-1): counts, percentage, state, and missed medicines."""
    service = StatusService(db)
    resolved_date = target_date or date.today()
    return await service.get_day_summary(elder_id, resolved_date, current_user)


@router.get("/{elder_id}/status/week", response_model=WeekSummaryResponse)
async def get_week_status(
    elder_id: uuid.UUID,
    week_start: Optional[date] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WeekSummaryResponse:
    """Get 7-day week status summary (STA-2, STA-4) with adherence percentages and missed highlights."""
    service = StatusService(db)
    # Default to Monday of current week if not provided
    today = date.today()
    resolved_start = week_start or (today - timedelta(days=today.weekday()))
    return await service.get_week_summary(elder_id, resolved_start, current_user)


@router.get("/{elder_id}/status/month", response_model=MonthSummaryResponse)
async def get_month_status(
    elder_id: uuid.UUID,
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MonthSummaryResponse:
    """Get month calendar status summary (STA-3) with adherence percentage and day-by-day status."""
    service = StatusService(db)
    today = date.today()
    resolved_year = year or today.year
    resolved_month = month or today.month
    return await service.get_month_summary(elder_id, resolved_year, resolved_month, current_user)


@router.post("/{elder_id}/close-day", response_model=DayClosureResponse)
async def trigger_day_close(
    elder_id: uuid.UUID,
    target_date: Optional[date] = Query(None, alias="date"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DayClosureResponse:
    """Close the day for an elder, marking un-taken scheduled doses as missed (Section 8.2)."""
    service = StatusService(db)
    resolved_date = target_date or date.today()
    return await service.close_elder_day(elder_id, resolved_date, actor=f"user:{current_user.id}")
