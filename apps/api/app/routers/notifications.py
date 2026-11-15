import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.models.user import User
from app.routers.deps import get_current_user
from app.schemas.notification import (
    NotificationListResponse,
    NotificationPreferencesResponse,
    NotificationPreferencesUpdateRequest,
    PushSubscribeRequest,
    WebhookStatusRequest,
)
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/api/v1", tags=["Notifications & Outbox"])


@router.get("/notifications", response_model=NotificationListResponse)
async def list_notifications(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationListResponse:
    """List in-app notifications and unread count (NOT-5)."""
    service = NotificationService(db)
    return await service.list_notifications(current_user, limit=limit, offset=offset)


@router.post("/notifications/{notification_id}/read", status_code=status.HTTP_200_OK)
async def mark_notification_read(
    notification_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Mark a single notification as read (NOT-5)."""
    service = NotificationService(db)
    await service.mark_as_read(current_user.id, notification_id)
    return {"status": "ok"}


@router.post("/notifications/read-all", status_code=status.HTTP_200_OK)
async def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Mark all unread notifications as read (NOT-5)."""
    service = NotificationService(db)
    await service.mark_all_read(current_user.id)
    return {"status": "ok"}


@router.get("/notification-preferences", response_model=NotificationPreferencesResponse)
async def get_notification_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationPreferencesResponse:
    """Get notification preferences grid and quiet hours (NOT-1, NOT-6)."""
    service = NotificationService(db)
    return await service.get_preferences(current_user)


@router.put("/notification-preferences", response_model=NotificationPreferencesResponse)
async def update_notification_preferences(
    payload: NotificationPreferencesUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationPreferencesResponse:
    """Update notification preferences grid and quiet hours (NOT-1, NOT-6)."""
    service = NotificationService(db)
    return await service.update_preferences(
        user=current_user,
        preferences=payload.preferences,
        quiet_start=payload.quiet_start,
        quiet_end=payload.quiet_end,
    )


@router.post("/push/subscribe", status_code=status.HTTP_201_CREATED)
async def subscribe_web_push(
    payload: PushSubscribeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Register a Web Push subscription."""
    service = NotificationService(db)
    await service.subscribe_push(
        user=current_user,
        endpoint=payload.endpoint,
        p256dh=payload.p256dh,
        auth=payload.auth,
    )
    return {"status": "subscribed"}


@router.delete("/push/subscribe", status_code=status.HTTP_200_OK)
async def unsubscribe_web_push(
    endpoint: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Unregister a Web Push subscription."""
    service = NotificationService(db)
    await service.unsubscribe_push(endpoint)
    return {"status": "unsubscribed"}


@router.post("/webhooks/{provider}/status", status_code=status.HTTP_200_OK)
async def provider_delivery_webhook(
    provider: str,
    payload: WebhookStatusRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Provider delivery callback for honest delivery status (NOT-3, Section 8.5)."""
    service = NotificationService(db)
    await service.update_delivery_status(
        provider_message_id=payload.provider_message_id,
        status=payload.status,
        error_code=payload.error_code,
    )
    return {"status": "acknowledged"}


@router.post("/outbox/process", status_code=status.HTTP_200_OK)
async def trigger_outbox_processing(
    batch_size: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Trigger an outbox processing cycle (worker endpoint)."""
    service = NotificationService(db)
    count = await service.process_outbox_batch(batch_size=batch_size)
    return {"dispatched_count": count}
