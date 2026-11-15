import uuid
from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.errors import ForbiddenError
from app.models.user import User
from app.routers.deps import CurrentActor, get_current_actor, get_current_user
from app.schemas.medicine import (
    DoseInstanceResponse,
    DuplicateCheckResponse,
    MarkDoseSkippedRequest,
    MedicineCreateRequest,
    MedicineResponse,
    MedicineUpdateRequest,
    PauseMedicineRequest,
    RefillRequest,
    StockAdjustRequest,
    StockEventResponse,
)
from app.services.medicine_service import MedicineService

router = APIRouter(prefix="/api/v1", tags=["Medicines & Doses"])


@router.get("/elders/{elder_id}/medicines", response_model=List[MedicineResponse])
async def list_medicines(
    elder_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[MedicineResponse]:
    """List medicines for an elder (MED-1 to MED-7)."""
    service = MedicineService(db)
    return await service.list_medicines(elder_id, current_user)


@router.post(
    "/elders/{elder_id}/medicines",
    response_model=MedicineResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_medicine(
    elder_id: uuid.UUID,
    payload: MedicineCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MedicineResponse:
    """Create a new scheduled or as-needed medicine (MED-1 to MED-4, MED-8)."""
    service = MedicineService(db)
    medicine, warning = await service.create_medicine(elder_id, current_user, payload)
    return await service.get_medicine(elder_id, medicine.id, current_user)


@router.get("/elders/{elder_id}/medicines/check-duplicate", response_model=DuplicateCheckResponse)
async def check_duplicate_medicine(
    elder_id: uuid.UUID,
    name: str = Query(..., min_length=1),
    strength: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DuplicateCheckResponse:
    """Check if medicine name and strength already exists for elder (MED-8)."""
    service = MedicineService(db)
    is_dup, warning = await service.check_duplicate(elder_id, name, strength)
    return DuplicateCheckResponse(is_duplicate=is_dup, warning=warning)


@router.get("/elders/{elder_id}/medicines/{medicine_id}", response_model=MedicineResponse)
async def get_medicine(
    elder_id: uuid.UUID,
    medicine_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MedicineResponse:
    """Get single medicine details."""
    service = MedicineService(db)
    return await service.get_medicine(elder_id, medicine_id, current_user)


@router.patch("/elders/{elder_id}/medicines/{medicine_id}", response_model=MedicineResponse)
async def update_medicine(
    elder_id: uuid.UUID,
    medicine_id: uuid.UUID,
    payload: MedicineUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MedicineResponse:
    """Update medicine fields or schedule (MED-6). Past doses never change."""
    service = MedicineService(db)
    return await service.update_medicine(elder_id, medicine_id, current_user, payload)


@router.post("/elders/{elder_id}/medicines/{medicine_id}/pause", status_code=status.HTTP_200_OK)
async def pause_medicine(
    elder_id: uuid.UUID,
    medicine_id: uuid.UUID,
    payload: Optional[PauseMedicineRequest] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Pause medicine schedule (MED-5)."""
    service = MedicineService(db)
    paused_until = payload.paused_until if payload else None
    await service.pause_medicine(elder_id, medicine_id, current_user, paused_until)
    return {"message": "Medicine schedule paused."}


@router.post("/elders/{elder_id}/medicines/{medicine_id}/resume", status_code=status.HTTP_200_OK)
async def resume_medicine(
    elder_id: uuid.UUID,
    medicine_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Resume paused medicine schedule (MED-5)."""
    service = MedicineService(db)
    await service.resume_medicine(elder_id, medicine_id, current_user)
    return {"message": "Medicine schedule resumed."}


@router.post("/elders/{elder_id}/medicines/{medicine_id}/end", status_code=status.HTTP_200_OK)
async def end_medicine(
    elder_id: uuid.UUID,
    medicine_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """End medicine (MED-7). Keeps history, removes future doses."""
    service = MedicineService(db)
    await service.end_medicine(elder_id, medicine_id, current_user)
    return {"message": "Medicine ended."}


# --- Doses Endpoints ---


@router.get("/elders/me/doses", response_model=List[DoseInstanceResponse])
async def list_current_elder_doses(
    target_date: Optional[date] = Query(None, alias="date"),
    actor: CurrentActor = Depends(get_current_actor),
    db: AsyncSession = Depends(get_db),
) -> List[DoseInstanceResponse]:
    """Fetch dose instances for the currently signed-in elder (ELD-V2)."""
    if not actor.is_elder or not actor.elder_id:
        raise ForbiddenError(detail="Only authenticated elders can access this endpoint.")
    service = MedicineService(db)
    resolved_date = target_date or date.today()
    return await service.get_doses_for_date(actor.elder_id, resolved_date, actor)


@router.get("/elders/{elder_id}/doses", response_model=List[DoseInstanceResponse])
async def list_elder_doses(
    elder_id: uuid.UUID,
    target_date: Optional[date] = Query(None, alias="date"),
    actor: CurrentActor = Depends(get_current_actor),
    db: AsyncSession = Depends(get_db),
) -> List[DoseInstanceResponse]:
    """Fetch dose instances for an elder on a date (default: today)."""
    service = MedicineService(db)
    resolved_date = target_date or date.today()
    return await service.get_doses_for_date(elder_id, resolved_date, actor)


@router.post("/doses/{dose_id}/take", response_model=DoseInstanceResponse)
async def mark_dose_taken(
    dose_id: uuid.UUID,
    actor: CurrentActor = Depends(get_current_actor),
    db: AsyncSession = Depends(get_db),
) -> DoseInstanceResponse:
    """Mark dose as taken (Section 2.2: Elder own or Caregiver on behalf). Starts 10-min undo window."""
    service = MedicineService(db)
    return await service.mark_dose_taken(dose_id, actor)


@router.post("/doses/{dose_id}/undo", response_model=DoseInstanceResponse)
async def undo_dose_taken(
    dose_id: uuid.UUID,
    actor: CurrentActor = Depends(get_current_actor),
    db: AsyncSession = Depends(get_db),
) -> DoseInstanceResponse:
    """Undo a dose marked taken within the 10-minute window (Section 8.3)."""
    service = MedicineService(db)
    return await service.undo_dose_taken(dose_id, actor)


@router.post("/doses/{dose_id}/skip", response_model=DoseInstanceResponse)
async def mark_dose_skipped(
    dose_id: uuid.UUID,
    payload: Optional[MarkDoseSkippedRequest] = None,
    actor: CurrentActor = Depends(get_current_actor),
    db: AsyncSession = Depends(get_db),
) -> DoseInstanceResponse:
    """Mark dose as skipped (Section 2.2: Caregiver only)."""
    service = MedicineService(db)
    reason = payload.reason if payload else None
    return await service.mark_dose_skipped(dose_id, actor, reason)


# --- Refill & Stock Ledger Endpoints (STK-1 to STK-5) ---


@router.post("/elders/{elder_id}/medicines/{medicine_id}/refill", response_model=MedicineResponse)
async def record_medicine_refill(
    elder_id: uuid.UUID,
    medicine_id: uuid.UUID,
    payload: RefillRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MedicineResponse:
    """Record a medicine refill event (STK-2, STK-5). Increases stock ledger."""
    service = MedicineService(db)
    return await service.record_refill(elder_id, medicine_id, current_user, payload)


@router.post("/elders/{elder_id}/medicines/{medicine_id}/stock-adjust", response_model=MedicineResponse)
async def adjust_medicine_stock(
    elder_id: uuid.UUID,
    medicine_id: uuid.UUID,
    payload: StockAdjustRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MedicineResponse:
    """Manually adjust medicine stock quantity (STK-2, STK-5)."""
    service = MedicineService(db)
    return await service.adjust_stock(elder_id, medicine_id, current_user, payload)


@router.get(
    "/elders/{elder_id}/medicines/{medicine_id}/stock-events",
    response_model=List[StockEventResponse],
)
async def list_stock_events(
    elder_id: uuid.UUID,
    medicine_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[StockEventResponse]:
    """Fetch stock ledger history for a medicine (STK-2, STK-5)."""
    service = MedicineService(db)
    return await service.list_stock_events(elder_id, medicine_id, current_user)
