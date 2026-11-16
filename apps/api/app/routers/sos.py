import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.errors import ForbiddenError
from app.models.user import User
from app.routers.deps import CurrentActor, get_current_actor, get_current_user
from app.schemas.sos import (
    ContactCreateRequest,
    ContactResponse,
    ContactUpdateRequest,
    ContactsReorderRequest,
    SosEventResponse,
    SosResolveRequest,
    SosTriggerRequest,
)
from app.services.sos_service import SosService

router = APIRouter(prefix="/api/v1", tags=["SOS & Contacts"])


# --- Contacts Endpoints (CON-1 to CON-6) ---


@router.get("/elders/me/contacts", response_model=List[ContactResponse])
async def list_current_elder_contacts(
    actor: CurrentActor = Depends(get_current_actor),
    db: AsyncSession = Depends(get_db),
) -> List[ContactResponse]:
    """List emergency and family contacts for the currently signed-in elder (ELD-V3)."""
    if not actor.is_elder or not actor.elder_id:
        raise ForbiddenError(detail="Only authenticated elders can access this endpoint.")
    service = SosService(db)
    return await service.list_contacts(actor.elder_id, actor)


@router.get("/elders/{elder_id}/contacts", response_model=List[ContactResponse])
async def list_emergency_contacts(
    elder_id: uuid.UUID,
    actor: CurrentActor = Depends(get_current_actor),
    db: AsyncSession = Depends(get_db),
) -> List[ContactResponse]:
    """List emergency contacts in escalation order (CON-1)."""
    service = SosService(db)
    return await service.list_contacts(elder_id, actor)


@router.post(
    "/elders/{elder_id}/contacts",
    response_model=ContactResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_emergency_contact(
    elder_id: uuid.UUID,
    payload: ContactCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ContactResponse:
    """Create an emergency contact with escalation order (CON-2)."""
    service = SosService(db)
    return await service.create_contact(elder_id, current_user, payload)


@router.patch("/elders/{elder_id}/contacts/{contact_id}", response_model=ContactResponse)
async def update_emergency_contact(
    elder_id: uuid.UUID,
    contact_id: uuid.UUID,
    payload: ContactUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ContactResponse:
    """Update contact details or escalation order (CON-3)."""
    service = SosService(db)
    return await service.update_contact(elder_id, contact_id, current_user, payload)


@router.delete("/elders/{elder_id}/contacts/{contact_id}", status_code=status.HTTP_200_OK)
async def delete_emergency_contact(
    elder_id: uuid.UUID,
    contact_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Delete an emergency contact (CON-4). Prevents deleting last contact."""
    service = SosService(db)
    await service.delete_contact(elder_id, contact_id, current_user)
    return {"message": "Emergency contact deleted."}


@router.post("/elders/{elder_id}/contacts/reorder", response_model=List[ContactResponse])
async def reorder_emergency_contacts(
    elder_id: uuid.UUID,
    payload: ContactsReorderRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[ContactResponse]:
    """Reorder escalation sequence for emergency contacts (CON-5)."""
    service = SosService(db)
    return await service.reorder_contacts(elder_id, current_user, payload.contact_ids)


class ContactMessagePayload(BaseModel):
    channel: str = "sms"  # "sms" or "whatsapp"
    custom_text: Optional[str] = None


@router.post("/elders/{elder_id}/contacts/{contact_id}/message", status_code=status.HTTP_200_OK)
async def send_contact_message(
    elder_id: uuid.UUID,
    contact_id: uuid.UUID,
    payload: Optional[ContactMessagePayload] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Send an instant SMS or WhatsApp alert to an emergency contact."""
    service = SosService(db)
    channel = payload.channel if payload else "sms"
    custom_text = payload.custom_text if payload else None
    return await service.send_contact_message(
        elder_id=elder_id,
        contact_id=contact_id,
        user=current_user,
        channel=channel,
        custom_text=custom_text,
    )


@router.post("/elders/{elder_id}/contacts/{contact_id}/call", status_code=status.HTTP_200_OK)
async def initiate_contact_call(
    elder_id: uuid.UUID,
    contact_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Initiate an outbound voice call to an emergency contact."""
    service = SosService(db)
    return await service.initiate_contact_call(
        elder_id=elder_id,
        contact_id=contact_id,
        user=current_user,
    )


# --- SOS Endpoints (SOS-1 to SOS-6) ---


@router.post("/elders/me/sos", response_model=SosEventResponse, status_code=status.HTTP_201_CREATED)
async def trigger_current_elder_sos(
    actor: CurrentActor = Depends(get_current_actor),
    db: AsyncSession = Depends(get_db),
) -> SosEventResponse:
    """Trigger emergency SOS alert from the elder's device (ELD-V4, SOS-1)."""
    if not actor.is_elder or not actor.elder_id:
        raise ForbiddenError(detail="Only authenticated elders can access this endpoint.")
    service = SosService(db)
    event = await service.trigger_sos(actor.elder_id, actor, source="web")
    res = await service.get_active_sos(actor.elder_id)
    return res or SosEventResponse(
        id=event.id,
        elder_id=event.elder_id,
        source=event.source,
        client_event_id=event.client_event_id,
        status=event.status,
        escalation_state=event.escalation_state,
        press_count=event.press_count,
        triggered_at=event.triggered_at,
        attempts=[],
    )


@router.post("/sos/trigger", response_model=SosEventResponse, status_code=status.HTTP_201_CREATED)
async def trigger_emergency_sos(
    payload: SosTriggerRequest,
    actor: CurrentActor = Depends(get_current_actor),
    db: AsyncSession = Depends(get_db),
) -> SosEventResponse:
    """Trigger emergency SOS alert from web app, elder device, or care team (SOS-1, SOS-2)."""
    service = SosService(db)
    event = await service.trigger_sos(
        payload.elder_id, actor, payload.source, payload.client_event_id
    )
    res = await service.get_active_sos(payload.elder_id)
    return res or SosEventResponse(
        id=event.id,
        elder_id=event.elder_id,
        source=event.source,
        client_event_id=event.client_event_id,
        status=event.status,
        escalation_state=event.escalation_state,
        press_count=event.press_count,
        triggered_at=event.triggered_at,
        attempts=[],
    )


@router.get("/elders/{elder_id}/sos/active", response_model=Optional[SosEventResponse])
async def get_active_emergency_sos(
    elder_id: uuid.UUID,
    actor: CurrentActor = Depends(get_current_actor),
    db: AsyncSession = Depends(get_db),
) -> Optional[SosEventResponse]:
    """Get active SOS event for persistent banner (SOS-3)."""
    service = SosService(db)
    return await service.get_active_sos(elder_id)


@router.get("/elders/{elder_id}/sos", response_model=List[SosEventResponse])
async def list_emergency_sos_history(
    elder_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[SosEventResponse]:
    """List SOS history with timeline of escalation attempts (SOS-6)."""
    service = SosService(db)
    return await service.list_sos_history(elder_id, current_user)


@router.post("/sos/{event_id}/acknowledge", status_code=status.HTTP_200_OK)
async def acknowledge_emergency_sos(
    event_id: uuid.UUID,
    contact_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Acknowledge an active SOS, pausing the escalation loop (SOS-4)."""
    service = SosService(db)
    await service.acknowledge_sos(event_id, contact_id)
    return {"message": "SOS alert acknowledged."}


@router.post("/sos/{event_id}/resolve", response_model=SosEventResponse)
async def resolve_emergency_sos(
    event_id: uuid.UUID,
    payload: Optional[SosResolveRequest] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SosEventResponse:
    """Mark an active SOS as handled/resolved (SOS-4). Dismisses live banner."""
    service = SosService(db)
    note = payload.note if payload else None
    return await service.resolve_sos(event_id, current_user, note)
