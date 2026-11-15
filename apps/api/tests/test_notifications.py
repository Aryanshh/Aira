import uuid
import datetime
from typing import Tuple
from zoneinfo import ZoneInfo
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now, ensure_utc
from app.models.notification import Notification, Outbox
from app.models.sos import DeliveryStatus
from app.models.user import Channel, NotifCategory, User
from app.services.notification_service import NotificationService


async def create_user_and_token(client: AsyncClient, email: str, name: str = "Test User") -> Tuple[str, uuid.UUID]:
    res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "StrongPassword999!",
            "full_name": name,
            "preferred_language": "hi",
            "timezone": "Asia/Kolkata",
        },
    )
    user_id = uuid.UUID(res.json()["id"])
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "StrongPassword999!"},
    )
    return login_res.json()["access_token"], user_id


@pytest.mark.asyncio
async def test_inbox_and_mark_read(client: AsyncClient, db_session: AsyncSession):
    token, user_id = await create_user_and_token(client, "inbox_user@example.com", "Inbox User")
    headers = {"Authorization": f"Bearer {token}"}

    # Seed notification
    notif = Notification(
        user_id=user_id,
        category=NotifCategory.MISSED,
        template_key="missed.summary",
        params={"elder": "दादाजी", "count": 2, "names": "Metformin, Amlodipine"},
    )
    db_session.add(notif)
    await db_session.commit()

    # 1. List notifications (NOT-5)
    list_res = await client.get("/api/v1/notifications", headers=headers)
    assert list_res.status_code == 200
    data = list_res.json()
    assert data["unread_count"] == 1
    assert len(data["notifications"]) == 1
    item = data["notifications"][0]
    assert item["id"] == str(notif.id)
    # Verify rendered in recipient's preferred language (hi)
    assert "दवा(एँ) छूट गईं" in item["rendered_text"]

    # 2. Mark single notification as read (NOT-5)
    read_res = await client.post(f"/api/v1/notifications/{notif.id}/read", headers=headers)
    assert read_res.status_code == 200

    list_res2 = await client.get("/api/v1/notifications", headers=headers)
    assert list_res2.json()["unread_count"] == 0

    # 3. Mark all read
    read_all_res = await client.post("/api/v1/notifications/read-all", headers=headers)
    assert read_all_res.status_code == 200


@pytest.mark.asyncio
async def test_notification_preferences_and_locking(client: AsyncClient):
    token, _ = await create_user_and_token(client, "pref_user@example.com", "Pref User")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Fetch default preferences grid (NOT-1)
    get_res = await client.get("/api/v1/notification-preferences", headers=headers)
    assert get_res.status_code == 200
    pref_data = get_res.json()
    assert len(pref_data["preferences"]) > 0
    assert pref_data["quiet_start"] == "22:00"
    assert pref_data["quiet_end"] == "07:00"

    # 2. In-app and push cannot be disabled for SOS (NOT-1 safety invariant)
    fail_payload = {
        "preferences": [
            {"category": "sos", "channel": "in_app", "enabled": False},
        ],
        "quiet_start": "23:00",
        "quiet_end": "06:00",
    }
    fail_res = await client.put("/api/v1/notification-preferences", headers=headers, json=fail_payload)
    assert fail_res.status_code == 422
    assert "cannot be disabled" in fail_res.json()["detail"]

    # 3. System in-app cannot be disabled
    fail_sys_payload = {
        "preferences": [
            {"category": "system", "channel": "in_app", "enabled": False},
        ],
    }
    fail_sys_res = await client.put("/api/v1/notification-preferences", headers=headers, json=fail_sys_payload)
    assert fail_sys_res.status_code == 422

    # 4. Valid update
    valid_payload = {
        "preferences": [
            {"category": "missed", "channel": "email", "enabled": False},
            {"category": "refill", "channel": "email", "enabled": True},
        ],
        "quiet_start": "23:00",
        "quiet_end": "06:30",
    }
    update_res = await client.put("/api/v1/notification-preferences", headers=headers, json=valid_payload)
    assert update_res.status_code == 200
    updated = update_res.json()
    assert updated["quiet_start"] == "23:00"
    assert updated["quiet_end"] == "06:30"


@pytest.mark.asyncio
async def test_outbox_processing_and_quiet_hours(client: AsyncClient, db_session: AsyncSession):
    token, user_id = await create_user_and_token(client, "outbox_user@example.com", "Outbox User")
    user = (await db_session.execute(select(User).where(User.id == user_id))).scalar_one()

    # Configure user with quiet hours that match current time
    tz = ZoneInfo("Asia/Kolkata")
    local_now = utc_now().astimezone(tz)
    user.quiet_start = (local_now - datetime.timedelta(hours=1)).time()
    user.quiet_end = (local_now + datetime.timedelta(hours=2)).time()
    await db_session.commit()

    service = NotificationService(db_session)
    assert service.is_in_quiet_hours(user) is True

    # Clear prior registration outbox items
    from sqlalchemy import delete
    await db_session.execute(delete(Outbox))
    await db_session.commit()

    # 1. Enqueue missed medicine notification on SMS (subject to quiet hours)
    missed_outbox = Outbox(
        channel="sms",
        recipient=str(user_id),
        template_key="missed.summary",
        language="en",
        params={"elder": "Dadaji", "count": 1, "names": "Aspirin"},
        dedupe_key=f"test:missed:{uuid.uuid4()}",
        status=DeliveryStatus.QUEUED,
    )
    db_session.add(missed_outbox)

    # 2. Enqueue emergency SOS notification on SMS (NOT subject to quiet hours, NOT-6)
    sos_outbox = Outbox(
        channel="sms",
        recipient=str(user_id),
        template_key="sos.alert",
        language="en",
        params={"elder": "Dadaji", "time": "12:00", "link": "http://test"},
        dedupe_key=f"test:sos:{uuid.uuid4()}",
        status=DeliveryStatus.QUEUED,
    )
    db_session.add(sos_outbox)
    await db_session.commit()

    # 3. Process Outbox batch (NOT-2, NOT-3, Section 8.5)
    dispatched = await service.process_outbox_batch()
    # Exactly 1 message should be dispatched (SOS); Missed should be deferred
    assert dispatched == 1

    await db_session.refresh(missed_outbox)
    await db_session.refresh(sos_outbox)

    # Missed remains QUEUED with next_attempt_at pushed into future
    assert missed_outbox.status == DeliveryStatus.QUEUED
    assert ensure_utc(missed_outbox.next_attempt_at) > utc_now()

    # SOS is marked SENT with provider_message_id (NOT-3: never delivered until confirmed)
    assert sos_outbox.status == DeliveryStatus.SENT
    assert sos_outbox.provider_message_id is not None
    assert sos_outbox.attempts == 1


@pytest.mark.asyncio
async def test_provider_webhook_honest_delivery(client: AsyncClient, db_session: AsyncSession):
    # Enqueue and send an outbox message
    outbox = Outbox(
        channel="sms",
        recipient="+919876543210",
        template_key="sos.alert",
        language="en",
        params={"elder": "Dadaji", "time": "14:00", "link": "http://test"},
        dedupe_key=f"webhook_test:{uuid.uuid4()}",
        status=DeliveryStatus.QUEUED,
    )
    db_session.add(outbox)
    await db_session.commit()

    service = NotificationService(db_session)
    await service.process_outbox_batch()
    await db_session.refresh(outbox)
    assert outbox.status == DeliveryStatus.SENT
    msg_id = outbox.provider_message_id

    # Webhook arrives confirming delivery (NOT-3, Section 8.5)
    wh_res = await client.post(
        "/api/v1/webhooks/twilio/status",
        json={"provider_message_id": msg_id, "status": "delivered"},
    )
    assert wh_res.status_code == 200

    await db_session.refresh(outbox)
    assert outbox.status == DeliveryStatus.DELIVERED


@pytest.mark.asyncio
async def test_push_subscription(client: AsyncClient):
    token, _ = await create_user_and_token(client, "push_user@example.com", "Push User")
    headers = {"Authorization": f"Bearer {token}"}

    sub_payload = {
        "endpoint": "https://push.example.com/sub/123",
        "p256dh": "BNcRdreALRF8FsE",
        "auth": "tBHItJI5svbQ",
    }
    res = await client.post("/api/v1/push/subscribe", headers=headers, json=sub_payload)
    assert res.status_code == 201

    del_res = await client.delete(
        "/api/v1/push/subscribe",
        headers=headers,
        params={"endpoint": "https://push.example.com/sub/123"},
    )
    assert del_res.status_code == 200
