import uuid
import pytest
from httpx import AsyncClient


async def create_user_and_token(client: AsyncClient, email: str, name: str = "Test User") -> str:
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "StrongPassword999!",
            "full_name": name,
            "preferred_language": "en",
        },
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "StrongPassword999!"},
    )
    return login_res.json()["access_token"]


async def create_elder_helper(client: AsyncClient, owner_token: str) -> dict:
    res = await client.post(
        "/api/v1/elders",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"full_name": "Harish Chandra", "preferred_name": "Pitaji", "day_close_time": "23:59"},
    )
    return res.json()


@pytest.mark.asyncio
async def test_contacts_crud_and_prevent_last_contact_deletion(client: AsyncClient):
    token = await create_user_and_token(client, "contact_owner@example.com", "Contact Owner")
    headers = {"Authorization": f"Bearer {token}"}
    creds = await create_elder_helper(client, token)
    elder_id = creds["elder_id"]

    # 1. Create primary emergency contact (CON-2)
    c1_res = await client.post(
        f"/api/v1/elders/{elder_id}/contacts",
        headers=headers,
        json={
            "full_name": "Dr. Sameer Verma",
            "role": "doctor",
            "phone_e164": "+919876543210",
            "escalation_order": 1,
            "preferred_channels": ["sms", "whatsapp"],
        },
    )
    assert c1_res.status_code == 201
    c1 = c1_res.json()
    assert c1["escalation_order"] == 1

    # 2. Create secondary contact
    c2_res = await client.post(
        f"/api/v1/elders/{elder_id}/contacts",
        headers=headers,
        json={
            "full_name": "Anita Verma (Neighbor)",
            "role": "neighbour",
            "phone_e164": "+919876543211",
            "escalation_order": 2,
        },
    )
    assert c2_res.status_code == 201
    c2 = c2_res.json()
    assert c2["escalation_order"] == 2

    # 3. List contacts in escalation order (CON-1)
    list_res = await client.get(f"/api/v1/elders/{elder_id}/contacts", headers=headers)
    assert list_res.status_code == 200
    contacts = list_res.json()
    assert len(contacts) == 2
    assert contacts[0]["id"] == c1["id"]
    assert contacts[1]["id"] == c2["id"]

    # 4. Reorder contacts (CON-5)
    reorder_res = await client.post(
        f"/api/v1/elders/{elder_id}/contacts/reorder",
        headers=headers,
        json={"contact_ids": [c2["id"], c1["id"]]},
    )
    assert reorder_res.status_code == 200
    reordered = reorder_res.json()
    assert reordered[0]["id"] == c2["id"]
    assert reordered[0]["escalation_order"] == 1
    assert reordered[1]["id"] == c1["id"]
    assert reordered[1]["escalation_order"] == 2

    # 5. Delete contact 2
    del_c2 = await client.delete(f"/api/v1/elders/{elder_id}/contacts/{c2['id']}", headers=headers)
    assert del_c2.status_code == 200

    # 6. Attempting to delete the last active contact fails (CON-4)
    last_del_fail = await client.delete(f"/api/v1/elders/{elder_id}/contacts/{c1['id']}", headers=headers)
    assert last_del_fail.status_code == 409
    assert last_del_fail.json()["code"] == "LAST_CONTACT_CANNOT_BE_DELETED"


@pytest.mark.asyncio
async def test_sos_trigger_escalation_and_live_banner(client: AsyncClient):
    token = await create_user_and_token(client, "sos_owner@example.com", "SOS Owner")
    headers = {"Authorization": f"Bearer {token}"}
    creds = await create_elder_helper(client, token)
    elder_id = creds["elder_id"]

    # Add emergency contact
    await client.post(
        f"/api/v1/elders/{elder_id}/contacts",
        headers=headers,
        json={
            "full_name": "Emergency Family",
            "role": "family",
            "phone_e164": "+919811112222",
            "preferred_channels": ["sms", "whatsapp"],
        },
    )

    # 1. Trigger SOS (SOS-1, SOS-2)
    trigger_res = await client.post(
        "/api/v1/sos/trigger",
        headers=headers,
        json={"elder_id": elder_id, "source": "web"},
    )
    assert trigger_res.status_code == 201
    sos_data = trigger_res.json()
    event_id = sos_data["id"]
    assert sos_data["status"] == "active"
    assert sos_data["escalation_state"] == "in_progress"
    assert sos_data["press_count"] == 1
    assert len(sos_data["attempts"]) >= 1

    # 2. Repeated trigger increments press count (idempotency/heartbeat)
    rep_res = await client.post(
        "/api/v1/sos/trigger",
        headers=headers,
        json={"elder_id": elder_id, "source": "web"},
    )
    assert rep_res.status_code == 201
    assert rep_res.json()["press_count"] == 2

    # 3. Active SOS query for live banner (SOS-3)
    active_res = await client.get(f"/api/v1/elders/{elder_id}/sos/active", headers=headers)
    assert active_res.status_code == 200
    active_data = active_res.json()
    assert active_data is not None
    assert active_data["id"] == event_id

    # 4. Acknowledge SOS (SOS-4)
    ack_res = await client.post(f"/api/v1/sos/{event_id}/acknowledge")
    assert ack_res.status_code == 200

    # 5. Resolve SOS (SOS-4)
    resolve_res = await client.post(
        f"/api/v1/sos/{event_id}/resolve",
        headers=headers,
        json={"note": "False alarm, elder accidentally leaned on button"},
    )
    assert resolve_res.status_code == 200

    # 6. Active SOS banner is now cleared
    active_after = await client.get(f"/api/v1/elders/{elder_id}/sos/active", headers=headers)
    assert active_after.json() is None

    # 7. SOS History lists the resolved event (SOS-6)
    history_res = await client.get(f"/api/v1/elders/{elder_id}/sos", headers=headers)
    assert history_res.status_code == 200
    history = history_res.json()
    assert len(history) == 1
    assert history[0]["status"] == "handled"
    assert history[0]["handled_at"] is not None
