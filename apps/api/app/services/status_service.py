import calendar
import collections
import uuid
from datetime import date, datetime, time, timedelta
from typing import List, Optional, Tuple
from zoneinfo import ZoneInfo
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ForbiddenError, NotFoundError
from app.core.time import ensure_utc, utc_now
from app.models.audit import AuditEvent
from app.models.dose import DayClosure, DoseInstance, DoseStatus
from app.models.elder import CareLink, Elder
from app.models.notification import Notification, Outbox
from app.models.user import NotifCategory, User
from app.schemas.status import (
    DayClosureResponse,
    DaySummaryResponse,
    MonthSummaryResponse,
    WeekSummaryResponse,
)


class StatusService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _require_care_access(self, elder_id: uuid.UUID, user: User) -> CareLink:
        stmt = select(CareLink).where(CareLink.elder_id == elder_id, CareLink.user_id == user.id)
        result = await self.db.execute(stmt)
        link = result.scalar_one_or_none()
        if not link:
            raise ForbiddenError(detail="You do not have access to this elder profile.")
        return link

    async def get_day_summary(
        self, elder_id: uuid.UUID, target_date: date, user: Optional[User] = None
    ) -> DaySummaryResponse:
        """Calculate day summary counts, percentage, state, and missed highlights (STA-1)."""
        if user:
            await self._require_care_access(elder_id, user)

        stmt = select(DoseInstance).where(
            DoseInstance.elder_id == elder_id,
            DoseInstance.scheduled_date == target_date,
        )
        result = await self.db.execute(stmt)
        doses = result.scalars().all()

        total = len(doses)
        taken = sum(1 for d in doses if d.status == DoseStatus.TAKEN)
        missed = sum(1 for d in doses if d.status == DoseStatus.MISSED)
        skipped = sum(1 for d in doses if d.status == DoseStatus.SKIPPED)

        pct = round((taken / total) * 100) if total > 0 else 100

        if total == 0:
            state = "no_doses"
        elif missed > 0:
            state = "has_missed"
        elif taken == total:
            state = "all_taken"
        else:
            state = "in_progress"

        missed_names = sorted(list(set(d.medicine_name_snapshot for d in doses if d.status == DoseStatus.MISSED)))

        return DaySummaryResponse(
            elder_id=elder_id,
            date=target_date,
            total_scheduled=total,
            taken_count=taken,
            missed_count=missed,
            skipped_count=skipped,
            adherence_pct=pct,
            state=state,
            missed_medicine_names=missed_names,
        )

    async def get_week_summary(
        self, elder_id: uuid.UUID, week_start: date, user: User
    ) -> WeekSummaryResponse:
        """Calculate weekly adherence, day chips, and missed highlights (STA-2, STA-4)."""
        await self._require_care_access(elder_id, user)

        days_summary: List[DaySummaryResponse] = []
        total_sched = 0
        total_taken = 0
        total_missed = 0
        missed_counter: collections.Counter = collections.Counter()

        for offset in range(7):
            d = week_start + timedelta(days=offset)
            summary = await self.get_day_summary(elder_id, d)
            days_summary.append(summary)

            total_sched += summary.total_scheduled
            total_taken += summary.taken_count
            total_missed += summary.missed_count

            for name in summary.missed_medicine_names:
                missed_counter[name] += 1

        overall_pct = round((total_taken / total_sched) * 100) if total_sched > 0 else 100

        # Format highlights (STA-4)
        highlights = [
            f"{name} ({count} missed)" if count > 1 else f"{name} (1 missed)"
            for name, count in missed_counter.most_common()
        ]

        return WeekSummaryResponse(
            elder_id=elder_id,
            week_start=week_start,
            week_end=week_start + timedelta(days=6),
            overall_adherence_pct=overall_pct,
            total_scheduled=total_sched,
            total_taken=total_taken,
            total_missed=total_missed,
            days=days_summary,
            missed_highlights=highlights,
        )

    async def get_month_summary(
        self, elder_id: uuid.UUID, year: int, month: int, user: User
    ) -> MonthSummaryResponse:
        """Calculate month calendar day summaries and overall adherence (STA-3)."""
        await self._require_care_access(elder_id, user)

        _, num_days = calendar.monthrange(year, month)
        days_summary: List[DaySummaryResponse] = []
        total_sched = 0
        total_taken = 0
        total_missed = 0

        for day in range(1, num_days + 1):
            d = date(year, month, day)
            summary = await self.get_day_summary(elder_id, d)
            days_summary.append(summary)

            total_sched += summary.total_scheduled
            total_taken += summary.taken_count
            total_missed += summary.missed_count

        overall_pct = round((total_taken / total_sched) * 100) if total_sched > 0 else 100

        return MonthSummaryResponse(
            elder_id=elder_id,
            year=year,
            month=month,
            overall_adherence_pct=overall_pct,
            total_scheduled=total_sched,
            total_taken=total_taken,
            total_missed=total_missed,
            days=days_summary,
        )

    # --- Day-Closing Worker (Section 8.2, Section 13) ---

    async def close_elder_day(
        self, elder_id: uuid.UUID, target_date: date, actor: str = "system:day_close"
    ) -> DayClosureResponse:
        """Close an elder's day, mark scheduled doses as missed, and notify care team (Section 8.2). Idempotent."""
        # 1. Idempotency check on DayClosure
        closure_stmt = select(DayClosure).where(
            DayClosure.elder_id == elder_id,
            DayClosure.closed_date == target_date,
        )
        existing_closure = (await self.db.execute(closure_stmt)).scalar_one_or_none()
        if existing_closure:
            return DayClosureResponse(
                elder_id=elder_id,
                closed_date=target_date,
                doses_marked_missed=0,
                already_closed=True,
            )

        # 2. Find pending scheduled doses for target_date
        pending_stmt = select(DoseInstance).where(
            DoseInstance.elder_id == elder_id,
            DoseInstance.scheduled_date == target_date,
            DoseInstance.status == DoseStatus.SCHEDULED,
        )
        pending_doses = (await self.db.execute(pending_stmt)).scalars().all()

        missed_count = len(pending_doses)
        missed_med_names = set()

        for dose in pending_doses:
            dose.status = DoseStatus.MISSED
            dose.resolved_on = target_date
            dose.resolved_by_actor = actor
            dose.updated_at = utc_now()
            missed_med_names.add(dose.medicine_name_snapshot)

        # 3. Create DayClosure record
        closure = DayClosure(
            elder_id=elder_id,
            closed_date=target_date,
            closed_at=utc_now(),
        )
        self.db.add(closure)

        # 4. If any doses were missed, notify care team (Section 8.2)
        if missed_count > 0:
            team_stmt = select(CareLink).where(CareLink.elder_id == elder_id)
            team_links = (await self.db.execute(team_stmt)).scalars().all()

            for link in team_links:
                notif = Notification(
                    user_id=link.user_id,
                    elder_id=elder_id,
                    category=NotifCategory.MISSED,
                    template_key="medicine.missed_alert",
                    params={
                        "elder_id": str(elder_id),
                        "date": str(target_date),
                        "missed_count": str(missed_count),
                        "medicines": ", ".join(sorted(list(missed_med_names))),
                    },
                )
                self.db.add(notif)

            audit = AuditEvent(
                elder_id=elder_id,
                actor_type="system",
                action="elder.day_closed_with_missed",
                entity="day_closure",
                entity_id=elder_id,
                meta={
                    "date": str(target_date),
                    "missed_count": missed_count,
                    "medicines": list(missed_med_names),
                },
            )
            self.db.add(audit)
        else:
            audit = AuditEvent(
                elder_id=elder_id,
                actor_type="system",
                action="elder.day_closed_clean",
                entity="day_closure",
                entity_id=elder_id,
                meta={"date": str(target_date), "missed_count": 0},
            )
            self.db.add(audit)

        await self.db.flush()

        return DayClosureResponse(
            elder_id=elder_id,
            closed_date=target_date,
            doses_marked_missed=missed_count,
            already_closed=False,
        )

    async def run_worker_day_closure_cycle(self) -> int:
        """Worker cycle: iterates over active elders and closes days where local time >= day_close_time."""
        stmt = select(Elder).where(Elder.archived_at.is_(None))
        elders = (await self.db.execute(stmt)).scalars().all()

        closed_count = 0
        now_utc = utc_now()

        for elder in elders:
            try:
                tz = ZoneInfo(elder.timezone)
            except Exception:
                tz = ZoneInfo("Asia/Kolkata")

            elder_local_now = now_utc.astimezone(tz)
            elder_today = elder_local_now.date()
            elder_current_time = elder_local_now.time()

            # Check if elder's current local time is past day_close_time
            if elder_current_time >= elder.day_close_time:
                res = await self.close_elder_day(elder.id, elder_today)
                if not res.already_closed:
                    closed_count += 1

            # Also check yesterday just in case worker was down at day_close_time
            yesterday = elder_today - timedelta(days=1)
            res_yest = await self.close_elder_day(elder.id, yesterday)
            if not res_yest.already_closed:
                closed_count += 1

        await self.db.commit()
        return closed_count
