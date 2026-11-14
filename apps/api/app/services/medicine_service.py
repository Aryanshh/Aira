import calendar
import math
import uuid
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import List, Optional, Tuple
from zoneinfo import ZoneInfo
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.core.time import ensure_utc, utc_now
from app.models.audit import AuditEvent
from app.models.dose import DoseInstance, DoseStatus
from app.models.elder import CareLink, Elder
from app.models.medicine import Medicine, MedicineSchedule, MedStatus, Recurrence, StockEvent
from app.models.user import CareRole, User
from app.routers.deps import CurrentActor
from app.schemas.medicine import (
    DoseInstanceResponse,
    MedicineCreateRequest,
    MedicineResponse,
    MedicineUpdateRequest,
    ScheduleSchema,
)


class MedicineService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _get_elder_today(self, timezone_str: str) -> date:
        try:
            tz = ZoneInfo(timezone_str)
        except Exception:
            tz = ZoneInfo("Asia/Kolkata")
        return datetime.now(tz).date()

    async def _require_medicine_manager(self, elder_id: uuid.UUID, user: User) -> CareLink:
        stmt = select(CareLink).where(CareLink.elder_id == elder_id, CareLink.user_id == user.id)
        result = await self.db.execute(stmt)
        link = result.scalar_one_or_none()
        if not link:
            raise ForbiddenError(detail="You do not have access to this elder.")

        if not (link.is_owner or link.role == CareRole.CAREGIVER or link.can_manage_medicines):
            raise ForbiddenError(detail="You do not have permission to manage medicines.")
        return link

    async def _require_care_access(self, elder_id: uuid.UUID, user: User) -> CareLink:
        stmt = select(CareLink).where(CareLink.elder_id == elder_id, CareLink.user_id == user.id)
        result = await self.db.execute(stmt)
        link = result.scalar_one_or_none()
        if not link:
            raise ForbiddenError(detail="You do not have access to this elder.")
        return link

    async def check_duplicate(self, elder_id: uuid.UUID, name: str, strength: Optional[str]) -> Tuple[bool, Optional[str]]:
        """Warn if an active medicine with the same name and strength exists (MED-8)."""
        stmt = select(Medicine).where(
            Medicine.elder_id == elder_id,
            func.lower(Medicine.name) == name.strip().lower(),
            Medicine.status == MedStatus.ACTIVE,
        )
        if strength:
            stmt = stmt.where(Medicine.strength == strength.strip())

        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            return True, f"A medicine named '{existing.name}' with strength '{existing.strength or 'N/A'}' already exists."
        return False, None

    async def create_medicine(
        self, elder_id: uuid.UUID, user: User, data: MedicineCreateRequest
    ) -> Tuple[Medicine, Optional[str]]:
        """Create a new medicine and its initial schedule version (MED-1 to MED-4, MED-8)."""
        await self._require_medicine_manager(elder_id, user)

        elder = (await self.db.execute(select(Elder).where(Elder.id == elder_id))).scalar_one_or_none()
        if not elder or elder.archived_at is not None:
            raise NotFoundError(detail="Elder not found or archived.")

        # Duplicate check warning
        is_dup, warning = await self.check_duplicate(elder_id, data.name, data.strength)

        elder_today = self._get_elder_today(elder.timezone)
        start_date = data.start_date or elder_today

        medicine = Medicine(
            elder_id=elder_id,
            name=data.name.strip(),
            strength=data.strength.strip() if data.strength else None,
            form=data.form.strip() if data.form else "tablet",
            dose_amount=data.dose_amount,
            dose_unit=data.dose_unit.strip() if data.dose_unit else "tablet",
            instructions=data.instructions.strip() if data.instructions else None,
            color_tag=data.color_tag.strip() if data.color_tag else None,
            as_needed=data.as_needed,
            status=MedStatus.ACTIVE,
            stock_quantity=data.stock_quantity,
            refill_threshold_days=data.refill_threshold_days,
            created_by=user.id,
        )
        self.db.add(medicine)
        await self.db.flush()

        # Initial stock ledger event if initial stock > 0
        if data.stock_quantity > 0:
            stock_event = StockEvent(
                medicine_id=medicine.id,
                delta=data.stock_quantity,
                reason="initial_stock",
                created_by=user.full_name,
            )
            self.db.add(stock_event)

        # Create schedule if not as-needed
        if not data.as_needed:
            schedule = MedicineSchedule(
                medicine_id=medicine.id,
                frequency=data.frequency or Recurrence.DAILY,
                interval_n=data.interval_n or 1,
                days_of_week=data.days_of_week,
                days_of_month=data.days_of_month,
                times_of_day=sorted(list(set(data.times_of_day or ["08:00"]))),
                start_date=start_date,
                end_date=data.end_date,
                anchor_date=data.anchor_date or start_date,
                effective_from=start_date,
                effective_to=data.end_date,
            )
            self.db.add(schedule)
            await self.db.flush()

            # Generate rolling 14-day doses
            await self.generate_doses(medicine, schedule, elder, start_date, start_date + timedelta(days=14))

        # Audit
        audit = AuditEvent(
            elder_id=elder_id,
            actor_type="user",
            actor_id=user.id,
            action="medicine.created",
            entity="medicine",
            entity_id=medicine.id,
            meta={"name": medicine.name},
        )
        self.db.add(audit)
        await self.db.flush()

        return medicine, warning

    async def list_medicines(self, elder_id: uuid.UUID, user: User) -> List[MedicineResponse]:
        """List medicines for an elder with active schedule and days remaining (STK-3)."""
        await self._require_care_access(elder_id, user)

        stmt = (
            select(Medicine)
            .where(Medicine.elder_id == elder_id)
            .order_by(Medicine.status.asc(), Medicine.created_at.desc())
        )
        result = await self.db.execute(stmt)
        medicines = result.scalars().all()

        responses = []
        for med in medicines:
            # Fetch active schedule
            sched_stmt = (
                select(MedicineSchedule)
                .where(MedicineSchedule.medicine_id == med.id)
                .order_by(MedicineSchedule.effective_from.desc())
            )
            sched = (await self.db.execute(sched_stmt)).scalars().first()

            # Calculate days remaining (STK-3)
            days_remaining = None
            if not med.as_needed and sched and med.status == MedStatus.ACTIVE:
                doses_per_day = len(sched.times_of_day)
                units_per_day = Decimal(str(doses_per_day)) * med.dose_amount
                if units_per_day > 0:
                    days_remaining = int(math.floor(float(med.stock_quantity / units_per_day)))

            active_sched_schema = None
            if sched:
                active_sched_schema = ScheduleSchema(
                    frequency=sched.frequency,
                    interval_n=sched.interval_n,
                    days_of_week=sched.days_of_week,
                    days_of_month=sched.days_of_month,
                    times_of_day=sched.times_of_day,
                    start_date=sched.start_date,
                    end_date=sched.end_date,
                    anchor_date=sched.anchor_date,
                    effective_from=sched.effective_from,
                    effective_to=sched.effective_to,
                )

            responses.append(
                MedicineResponse(
                    id=med.id,
                    elder_id=med.elder_id,
                    name=med.name,
                    strength=med.strength,
                    form=med.form,
                    dose_amount=med.dose_amount,
                    dose_unit=med.dose_unit,
                    instructions=med.instructions,
                    color_tag=med.color_tag,
                    as_needed=med.as_needed,
                    status=med.status,
                    paused_until=med.paused_until,
                    ended_on=med.ended_on,
                    stock_quantity=med.stock_quantity,
                    refill_threshold_days=med.refill_threshold_days,
                    days_remaining=days_remaining,
                    active_schedule=active_sched_schema,
                    created_at=med.created_at,
                )
            )
        return responses

    async def get_medicine(self, elder_id: uuid.UUID, medicine_id: uuid.UUID, user: User) -> MedicineResponse:
        """Get single medicine details."""
        await self._require_care_access(elder_id, user)
        stmt = select(Medicine).where(Medicine.id == medicine_id, Medicine.elder_id == elder_id)
        med = (await self.db.execute(stmt)).scalar_one_or_none()
        if not med:
            raise NotFoundError(detail="Medicine not found.")

        sched_stmt = (
            select(MedicineSchedule)
            .where(MedicineSchedule.medicine_id == med.id)
            .order_by(MedicineSchedule.effective_from.desc())
        )
        sched = (await self.db.execute(sched_stmt)).scalars().first()

        days_remaining = None
        if not med.as_needed and sched and med.status == MedStatus.ACTIVE:
            doses_per_day = len(sched.times_of_day)
            units_per_day = Decimal(str(doses_per_day)) * med.dose_amount
            if units_per_day > 0:
                days_remaining = int(math.floor(float(med.stock_quantity / units_per_day)))

        active_sched_schema = None
        if sched:
            active_sched_schema = ScheduleSchema(
                frequency=sched.frequency,
                interval_n=sched.interval_n,
                days_of_week=sched.days_of_week,
                days_of_month=sched.days_of_month,
                times_of_day=sched.times_of_day,
                start_date=sched.start_date,
                end_date=sched.end_date,
                anchor_date=sched.anchor_date,
                effective_from=sched.effective_from,
                effective_to=sched.effective_to,
            )

        return MedicineResponse(
            id=med.id,
            elder_id=med.elder_id,
            name=med.name,
            strength=med.strength,
            form=med.form,
            dose_amount=med.dose_amount,
            dose_unit=med.dose_unit,
            instructions=med.instructions,
            color_tag=med.color_tag,
            as_needed=med.as_needed,
            status=med.status,
            paused_until=med.paused_until,
            ended_on=med.ended_on,
            stock_quantity=med.stock_quantity,
            refill_threshold_days=med.refill_threshold_days,
            days_remaining=days_remaining,
            active_schedule=active_sched_schema,
            created_at=med.created_at,
        )

    async def update_medicine(
        self, elder_id: uuid.UUID, medicine_id: uuid.UUID, user: User, data: MedicineUpdateRequest
    ) -> MedicineResponse:
        """Edit medicine properties or schedule version (MED-6). Past doses never change."""
        await self._require_medicine_manager(elder_id, user)

        med = (
            await self.db.execute(
                select(Medicine).where(Medicine.id == medicine_id, Medicine.elder_id == elder_id)
            )
        ).scalar_one_or_none()
        if not med:
            raise NotFoundError(detail="Medicine not found.")

        elder = (await self.db.execute(select(Elder).where(Elder.id == elder_id))).scalar_one()
        elder_today = self._get_elder_today(elder.timezone)

        # Update metadata
        if data.name is not None:
            med.name = data.name.strip()
        if data.strength is not None:
            med.strength = data.strength.strip() if data.strength else None
        if data.form is not None:
            med.form = data.form.strip() if data.form else "tablet"
        if data.dose_amount is not None:
            med.dose_amount = data.dose_amount
        if data.dose_unit is not None:
            med.dose_unit = data.dose_unit.strip() if data.dose_unit else "tablet"
        if data.instructions is not None:
            med.instructions = data.instructions.strip() if data.instructions else None
        if data.color_tag is not None:
            med.color_tag = data.color_tag.strip() if data.color_tag else None
        if data.refill_threshold_days is not None:
            med.refill_threshold_days = data.refill_threshold_days

        # Check if schedule parameters changed
        schedule_changed = any([
            data.frequency is not None,
            data.interval_n is not None,
            data.days_of_week is not None,
            data.days_of_month is not None,
            data.times_of_day is not None,
            data.end_date is not None,
        ])

        if schedule_changed and not med.as_needed:
            # MED-6: edits take effect from an effective date (default: tomorrow)
            effective_from = data.effective_from or (elder_today + timedelta(days=1))

            # Fetch active schedule
            latest_sched_stmt = (
                select(MedicineSchedule)
                .where(MedicineSchedule.medicine_id == med.id)
                .order_by(MedicineSchedule.effective_from.desc())
            )
            old_sched = (await self.db.execute(latest_sched_stmt)).scalars().first()

            if old_sched:
                # Close old schedule at effective_from - 1 day
                old_sched.effective_to = effective_from - timedelta(days=1)

            # Create new schedule version
            new_sched = MedicineSchedule(
                medicine_id=med.id,
                frequency=data.frequency or (old_sched.frequency if old_sched else Recurrence.DAILY),
                interval_n=data.interval_n or (old_sched.interval_n if old_sched else 1),
                days_of_week=data.days_of_week if data.days_of_week is not None else (old_sched.days_of_week if old_sched else None),
                days_of_month=data.days_of_month if data.days_of_month is not None else (old_sched.days_of_month if old_sched else None),
                times_of_day=sorted(list(set(data.times_of_day or (old_sched.times_of_day if old_sched else ["08:00"])))),
                start_date=effective_from,
                end_date=data.end_date if data.end_date is not None else (old_sched.end_date if old_sched else None),
                anchor_date=old_sched.anchor_date if old_sched else effective_from,
                effective_from=effective_from,
                effective_to=data.end_date if data.end_date is not None else (old_sched.end_date if old_sched else None),
            )
            self.db.add(new_sched)
            await self.db.flush()

            # Remove future scheduled doses starting from effective_from that were not resolved
            del_future_stmt = delete(DoseInstance).where(
                DoseInstance.medicine_id == med.id,
                DoseInstance.scheduled_date >= effective_from,
                DoseInstance.status == DoseStatus.SCHEDULED,
            )
            await self.db.execute(del_future_stmt)

            # Generate new doses from effective_from to effective_from + 14 days
            await self.generate_doses(med, new_sched, elder, effective_from, effective_from + timedelta(days=14))

        await self.db.flush()
        return await self.get_medicine(elder_id, medicine_id, user)

    async def pause_medicine(
        self, elder_id: uuid.UUID, medicine_id: uuid.UUID, user: User, paused_until: Optional[date]
    ) -> None:
        """Pause a medicine (MED-5). Deletes future scheduled doses."""
        await self._require_medicine_manager(elder_id, user)

        med = (
            await self.db.execute(
                select(Medicine).where(Medicine.id == medicine_id, Medicine.elder_id == elder_id)
            )
        ).scalar_one_or_none()
        if not med:
            raise NotFoundError(detail="Medicine not found.")

        elder = (await self.db.execute(select(Elder).where(Elder.id == elder_id))).scalar_one()
        elder_today = self._get_elder_today(elder.timezone)

        med.status = MedStatus.PAUSED
        med.paused_until = paused_until

        # Delete future scheduled doses from today
        del_stmt = delete(DoseInstance).where(
            DoseInstance.medicine_id == med.id,
            DoseInstance.scheduled_date >= elder_today,
            DoseInstance.status == DoseStatus.SCHEDULED,
        )
        await self.db.execute(del_stmt)
        await self.db.flush()

    async def resume_medicine(self, elder_id: uuid.UUID, medicine_id: uuid.UUID, user: User) -> None:
        """Resume a paused medicine (MED-5). Regenerates doses."""
        await self._require_medicine_manager(elder_id, user)

        med = (
            await self.db.execute(
                select(Medicine).where(Medicine.id == medicine_id, Medicine.elder_id == elder_id)
            )
        ).scalar_one_or_none()
        if not med:
            raise NotFoundError(detail="Medicine not found.")

        elder = (await self.db.execute(select(Elder).where(Elder.id == elder_id))).scalar_one()
        elder_today = self._get_elder_today(elder.timezone)

        med.status = MedStatus.ACTIVE
        med.paused_until = None

        if not med.as_needed:
            # Fetch active schedule
            latest_sched_stmt = (
                select(MedicineSchedule)
                .where(MedicineSchedule.medicine_id == med.id)
                .order_by(MedicineSchedule.effective_from.desc())
            )
            sched = (await self.db.execute(latest_sched_stmt)).scalars().first()
            if sched:
                await self.generate_doses(med, sched, elder, elder_today, elder_today + timedelta(days=14))

        await self.db.flush()

    async def end_medicine(self, elder_id: uuid.UUID, medicine_id: uuid.UUID, user: User) -> None:
        """End a medicine (MED-7). Keeps history, deletes future scheduled doses."""
        await self._require_medicine_manager(elder_id, user)

        med = (
            await self.db.execute(
                select(Medicine).where(Medicine.id == medicine_id, Medicine.elder_id == elder_id)
            )
        ).scalar_one_or_none()
        if not med:
            raise NotFoundError(detail="Medicine not found.")

        elder = (await self.db.execute(select(Elder).where(Elder.id == elder_id))).scalar_one()
        elder_today = self._get_elder_today(elder.timezone)

        med.status = MedStatus.ENDED
        med.ended_on = elder_today

        # Delete future scheduled doses from tomorrow
        del_stmt = delete(DoseInstance).where(
            DoseInstance.medicine_id == med.id,
            DoseInstance.scheduled_date > elder_today,
            DoseInstance.status == DoseStatus.SCHEDULED,
        )
        await self.db.execute(del_stmt)
        await self.db.flush()

    # --- Recurrence and Dose Generation Engine (Section 8.1) ---

    async def generate_doses(
        self,
        medicine: Medicine,
        schedule: MedicineSchedule,
        elder: Elder,
        start_date: date,
        end_date: date,
    ) -> int:
        """Generate dose instances for a medicine schedule in a date window."""
        if medicine.as_needed or medicine.status != MedStatus.ACTIVE:
            return 0

        tz = ZoneInfo(elder.timezone)
        count = 0

        current = start_date
        while current <= end_date:
            # Check schedule boundaries
            if current < schedule.start_date:
                current += timedelta(days=1)
                continue
            if schedule.end_date and current > schedule.end_date:
                break
            if schedule.effective_to and current > schedule.effective_to:
                break

            should_schedule = False

            if schedule.frequency == Recurrence.DAILY:
                should_schedule = True
            elif schedule.frequency == Recurrence.WEEKLY:
                # days_of_week: 1 (Mon) .. 7 (Sun)
                if schedule.days_of_week and current.isoweekday() in schedule.days_of_week:
                    should_schedule = True
            elif schedule.frequency == Recurrence.EVERY_N_DAYS:
                anchor = schedule.anchor_date or schedule.start_date
                if (current - anchor).days % schedule.interval_n == 0:
                    should_schedule = True
            elif schedule.frequency == Recurrence.MONTHLY:
                if schedule.days_of_month:
                    # If target day exceeds days in month, clamp to last day of month
                    _, max_days_in_month = calendar.monthrange(current.year, current.month)
                    for target_dom in schedule.days_of_month:
                        clamped_dom = min(target_dom, max_days_in_month)
                        if current.day == clamped_dom:
                            should_schedule = True
                            break

            if should_schedule:
                for time_str in schedule.times_of_day:
                    parsed_time = time.fromisoformat(time_str)

                    # Compute localized scheduled_at (UTC)
                    local_dt = datetime.combine(current, parsed_time, tzinfo=tz)
                    scheduled_at = local_dt.astimezone(ZoneInfo("UTC"))

                    # Check idempotency
                    exists_stmt = select(DoseInstance).where(
                        DoseInstance.medicine_id == medicine.id,
                        DoseInstance.scheduled_date == current,
                        DoseInstance.scheduled_time == parsed_time,
                    )
                    exists = (await self.db.execute(exists_stmt)).scalar_one_or_none()

                    if not exists:
                        dose = DoseInstance(
                            elder_id=elder.id,
                            medicine_id=medicine.id,
                            schedule_id=schedule.id,
                            scheduled_date=current,
                            scheduled_time=parsed_time,
                            scheduled_at=scheduled_at,
                            medicine_name_snapshot=medicine.name,
                            dose_label_snapshot=f"{medicine.dose_amount} {medicine.dose_unit}",
                            status=DoseStatus.SCHEDULED,
                        )
                        self.db.add(dose)
                        count += 1

            current += timedelta(days=1)

        await self.db.flush()
        return count

    # --- Dose Retrieval and Actions (Section 8.3) ---

    async def get_doses_for_date(
        self, elder_id: uuid.UUID, target_date: date, actor: CurrentActor
    ) -> List[DoseInstanceResponse]:
        """Fetch doses for an elder on a specific date (Section 2.2)."""
        if actor.is_elder:
            if actor.elder_id != elder_id:
                raise ForbiddenError(detail="Elders can only view their own doses.")
        else:
            await self._require_care_access(elder_id, actor.user)  # type: ignore

        stmt = (
            select(DoseInstance, Medicine)
            .join(Medicine, Medicine.id == DoseInstance.medicine_id)
            .where(
                DoseInstance.elder_id == elder_id,
                DoseInstance.scheduled_date == target_date,
            )
            .order_by(DoseInstance.scheduled_time.asc())
        )
        result = await self.db.execute(stmt)
        rows = result.all()

        responses = []
        now_utc = utc_now()

        for dose, med in rows:
            # Check 10-minute undo availability
            can_undo = False
            if dose.status == DoseStatus.TAKEN and dose.updated_at:
                can_undo = (ensure_utc(dose.updated_at) + timedelta(minutes=10)) >= now_utc

            responses.append(
                DoseInstanceResponse(
                    id=dose.id,
                    elder_id=dose.elder_id,
                    medicine_id=dose.medicine_id,
                    schedule_id=dose.schedule_id,
                    scheduled_date=dose.scheduled_date,
                    scheduled_time=dose.scheduled_time,
                    scheduled_at=dose.scheduled_at,
                    medicine_name=dose.medicine_name_snapshot,
                    dose_label=dose.dose_label_snapshot,
                    instructions=med.instructions,
                    color_tag=med.color_tag,
                    status=dose.status,
                    can_undo=can_undo,
                )
            )
        return responses

    async def mark_dose_taken(self, dose_id: uuid.UUID, actor: CurrentActor) -> DoseInstanceResponse:
        """Mark dose as taken (Section 2.2: Caregiver on behalf or Elder own). Updates stock ledger."""
        stmt = select(DoseInstance, Medicine).join(Medicine, Medicine.id == DoseInstance.medicine_id).where(DoseInstance.id == dose_id)
        row = (await self.db.execute(stmt)).first()
        if not row:
            raise NotFoundError(detail="Dose instance not found.")

        dose, med = row

        # Permission verification
        actor_label = ""
        if actor.is_elder:
            if actor.elder_id != dose.elder_id:
                raise ForbiddenError(detail="Cannot mark doses for another elder.")
            actor_label = "elder"
        else:
            link = await self._require_care_access(dose.elder_id, actor.user)  # type: ignore
            if not (link.role == CareRole.CAREGIVER or link.is_owner):
                raise ForbiddenError(detail="Only caregivers can mark doses taken on behalf of an elder.")
            actor_label = f"user:{actor.user.id}"  # type: ignore

        dose.status = DoseStatus.TAKEN
        dose.resolved_on = dose.scheduled_date
        dose.resolved_by_actor = actor_label
        dose.updated_at = utc_now()

        # Update stock ledger (STK-2: decrement dose_amount)
        med.stock_quantity = max(Decimal("0.0"), med.stock_quantity - med.dose_amount)
        stock_event = StockEvent(
            medicine_id=med.id,
            delta=-med.dose_amount,
            reason="dose_taken",
            created_by=actor_label,
        )
        self.db.add(stock_event)
        await self.db.flush()

        return DoseInstanceResponse(
            id=dose.id,
            elder_id=dose.elder_id,
            medicine_id=dose.medicine_id,
            schedule_id=dose.schedule_id,
            scheduled_date=dose.scheduled_date,
            scheduled_time=dose.scheduled_time,
            scheduled_at=dose.scheduled_at,
            medicine_name=dose.medicine_name_snapshot,
            dose_label=dose.dose_label_snapshot,
            instructions=med.instructions,
            color_tag=med.color_tag,
            status=dose.status,
            can_undo=True,
        )

    async def undo_dose_taken(self, dose_id: uuid.UUID, actor: CurrentActor) -> DoseInstanceResponse:
        """Undo a dose marked taken within the 10-minute window (Section 8.3). Restores stock."""
        stmt = select(DoseInstance, Medicine).join(Medicine, Medicine.id == DoseInstance.medicine_id).where(DoseInstance.id == dose_id)
        row = (await self.db.execute(stmt)).first()
        if not row:
            raise NotFoundError(detail="Dose instance not found.")

        dose, med = row

        if dose.status != DoseStatus.TAKEN:
            raise ConflictError(detail="Only taken doses can be undone.", code="NOT_TAKEN")

        # Check 10-minute rule
        if ensure_utc(dose.updated_at) + timedelta(minutes=10) < utc_now():
            raise ConflictError(
                detail="Dose action cannot be undone after 10 minutes.",
                code="CANNOT_UNDO_EXPIRED",
            )

        # Actor permission
        if actor.is_elder:
            if actor.elder_id != dose.elder_id:
                raise ForbiddenError(detail="Cannot undo doses for another elder.")
        else:
            link = await self._require_care_access(dose.elder_id, actor.user)  # type: ignore
            if not (link.role == CareRole.CAREGIVER or link.is_owner):
                raise ForbiddenError(detail="Only caregivers can undo doses on behalf of an elder.")

        dose.status = DoseStatus.SCHEDULED
        dose.resolved_on = None
        dose.resolved_by_actor = None
        dose.updated_at = utc_now()

        # Restore stock ledger (STK-2: +dose_amount)
        med.stock_quantity += med.dose_amount
        stock_event = StockEvent(
            medicine_id=med.id,
            delta=med.dose_amount,
            reason="dose_undo",
            created_by=f"undo:{actor.actor_type}",
        )
        self.db.add(stock_event)
        await self.db.flush()

        return DoseInstanceResponse(
            id=dose.id,
            elder_id=dose.elder_id,
            medicine_id=dose.medicine_id,
            schedule_id=dose.schedule_id,
            scheduled_date=dose.scheduled_date,
            scheduled_time=dose.scheduled_time,
            scheduled_at=dose.scheduled_at,
            medicine_name=dose.medicine_name_snapshot,
            dose_label=dose.dose_label_snapshot,
            instructions=med.instructions,
            color_tag=med.color_tag,
            status=dose.status,
            can_undo=False,
        )

    async def mark_dose_skipped(
        self, dose_id: uuid.UUID, actor: CurrentActor, reason: Optional[str]
    ) -> DoseInstanceResponse:
        """Mark dose as skipped (Section 2.2: Caregiver only)."""
        if actor.is_elder:
            raise ForbiddenError(detail="Elders cannot mark doses as skipped. Contact your caregiver.")

        stmt = select(DoseInstance, Medicine).join(Medicine, Medicine.id == DoseInstance.medicine_id).where(DoseInstance.id == dose_id)
        row = (await self.db.execute(stmt)).first()
        if not row:
            raise NotFoundError(detail="Dose instance not found.")

        dose, med = row

        link = await self._require_care_access(dose.elder_id, actor.user)  # type: ignore
        if not (link.role == CareRole.CAREGIVER or link.is_owner):
            raise ForbiddenError(detail="Only caregivers can mark doses as skipped.")

        dose.status = DoseStatus.SKIPPED
        dose.resolved_on = dose.scheduled_date
        dose.resolved_by_actor = f"user:{actor.user.id}"  # type: ignore
        dose.updated_at = utc_now()
        await self.db.flush()

        return DoseInstanceResponse(
            id=dose.id,
            elder_id=dose.elder_id,
            medicine_id=dose.medicine_id,
            schedule_id=dose.schedule_id,
            scheduled_date=dose.scheduled_date,
            scheduled_time=dose.scheduled_time,
            scheduled_at=dose.scheduled_at,
            medicine_name=dose.medicine_name_snapshot,
            dose_label=dose.dose_label_snapshot,
            instructions=med.instructions,
            color_tag=med.color_tag,
            status=dose.status,
            can_undo=False,
        )
