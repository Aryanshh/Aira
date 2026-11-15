import uuid
from datetime import date
import pytest
from httpx import AsyncClient

from app.models.dose import DoseStatus


async def create_caregiver_and_elder(client: AsyncClient):
    # Register caregiver
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "caregiver_elder_test@example.com",
            "password": "StrongPassword999!",
            "full_name": "Suresh Caregiver",
            "preferred_language": "en",
        },
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "caregiver_elder_test@example.com", "password": "StrongPassword999!"},
    )
    cg_token = login_res.json()["access_token"]
    cg_headers = {"Authorization": f"Bearer {cg_token}"}

    # Create elder
    creds_res = await client.post(
        "/api/v1/elders",
        headers=cg_headers,
        json={
            "full_name": "Devi Prasad",
            "preferred_name": "Dadaji",
            "language": "hi",
            "text_size": 1,
            "day_close_time": "23:59",
        },
    )
    creds = creds_res.json()
    elder_id = creds["elder_id"]
    access_code = creds["access_code"]
    pin = creds["pin"]

    # Login as elder
    elder_login_res = await client.post(
        "/api/v1/auth/elder/login",
        json={"access_code": access_code, "pin": pin, "device_label": "Tablet-1"},
    )
    elder_token = elder_login_res.json()["access_token"]
    elder_headers = {"Authorization": f"Bearer {elder_token}"}

    return {
        "cg_headers": cg_headers,
        "elder_headers": elder_headers,
        "elder_id": elder_id,
    }


@pytest.mark.asyncio
async def test_elder_profile_and_preferences(client: AsyncClient):
    setup = await create_caregiver_and_elder(client)
    elder_headers = setup["elder_headers"]
    cg_headers = setup["cg_headers"]

    # 1. Elder fetches own profile (ELD-V1)
    res = await client.get("/api/v1/elders/me/profile", headers=elder_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["preferred_name"] == "Dadaji"
    assert data["language"] == "hi"
    assert data["text_size"] == 1

    # 2. Elder updates language and text size (Section 2.2)
    patch_res = await client.patch(
        "/api/v1/elders/me/preferences",
        headers=elder_headers,
        json={"language": "en", "text_size": 2},
    )
    assert patch_res.status_code == 200
    updated = patch_res.json()
    assert updated["language"] == "en"
    assert updated["text_size"] == 2

    # 3. Non-elder actor forbidden
    forbidden_res = await client.get("/api/v1/elders/me/profile", headers=cg_headers)
    assert forbidden_res.status_code == 403


@pytest.mark.asyncio
async def test_elder_today_doses_and_take_undo(client: AsyncClient):
    setup = await create_caregiver_and_elder(client)
    cg_headers = setup["cg_headers"]
    elder_headers = setup["elder_headers"]
    elder_id = setup["elder_id"]

    # 1. Caregiver schedules a medicine
    med_res = await client.post(
        f"/api/v1/elders/{elder_id}/medicines",
        headers=cg_headers,
        json={
            "name": "Metformin",
            "strength": "500 mg",
            "form": "tablet",
            "dose_amount": 1,
            "dose_unit": "tablet",
            "instructions": "After breakfast",
            "color_tag": "#10B981",
            "initial_stock": 30,
            "schedule": {
                "frequency": "daily",
                "times_of_day": ["08:30"],
                "start_date": date.today().isoformat(),
            },
        },
    )
    assert med_res.status_code == 201

    # 2. Elder lists today's doses (ELD-V2)
    doses_res = await client.get("/api/v1/elders/me/doses", headers=elder_headers)
    assert doses_res.status_code == 200
    doses = doses_res.json()
    assert len(doses) >= 1
    dose = doses[0]
    assert dose["medicine_name"] == "Metformin"
    assert dose["instructions"] == "After breakfast"
    assert dose["status"] == "scheduled"
    assert dose["can_undo"] is False

    # 3. Elder marks dose as taken ("I took it")
    take_res = await client.post(f"/api/v1/doses/{dose['id']}/take", headers=elder_headers)
    assert take_res.status_code == 200
    taken_dose = take_res.json()
    assert taken_dose["status"] == "taken"
    assert taken_dose["can_undo"] is True

    # 4. Elder undoes taken marking within 10 minutes
    undo_res = await client.post(f"/api/doses/{dose['id']}/undo", headers=elder_headers)
    # router path is /api/v1/doses/{id}/undo
    undo_res = await client.post(f"/api/v1/doses/{dose['id']}/undo", headers=elder_headers)
    assert undo_res.status_code == 200
    reverted_dose = undo_res.json()
    assert reverted_dose["status"] == "scheduled"


@pytest.mark.asyncio
async def test_elder_contacts_and_sos(client: AsyncClient):
    setup = await create_caregiver_and_elder(client)
    cg_headers = setup["cg_headers"]
    elder_headers = setup["elder_headers"]
    elder_id = setup["elder_id"]

    # 1. Caregiver adds emergency contacts
    await client.post(
        f"/api/v1/elders/{elder_id}/contacts",
        headers=cg_headers,
        json={
            "full_name": "Anil Sharma (Son)",
            "role": "family",
            "phone_e164": "+919876543210",
            "escalation_order": 1,
            "preferred_channels": ["sms", "whatsapp"],
        },
    )

    # 2. Elder fetches contact list (ELD-V3)
    contacts_res = await client.get("/api/v1/elders/me/contacts", headers=elder_headers)
    assert contacts_res.status_code == 200
    contacts = contacts_res.json()
    assert len(contacts) == 1
    assert contacts[0]["full_name"] == "Anil Sharma (Son)"
    assert contacts[0]["phone_e164"] == "+919876543210"

    # 3. Elder triggers SOS (ELD-V4)
    sos_res = await client.post("/api/v1/elders/me/sos", headers=elder_headers)
    assert sos_res.status_code == 201
    sos_event = sos_res.json()
    assert sos_event["source"] == "web"
    assert sos_event["status"] == "active"
