import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


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
        json={"full_name": "Savitri Devi", "preferred_name": "Amma", "day_close_time": "23:59"},
    )
    return res.json()


@pytest.mark.asyncio
async def test_create_daily_medicine_and_dose_generation(client: AsyncClient):
    token = await create_user_and_token(client, "med_owner1@example.com", "Med Owner 1")
    headers = {"Authorization": f"Bearer {token}"}
    creds = await create_elder_helper(client, token)
    elder_id = creds["elder_id"]

    today = date.today()
    payload = {
        "name": "Metformin",
        "strength": "500 mg",
        "form": "tablet",
        "dose_amount": 1.0,
        "dose_unit": "tablet",
        "instructions": "After dinner",
        "as_needed": False,
        "frequency": "daily",
        "times_of_day": ["08:00", "20:00"],
        "start_date": str(today),
        "stock_quantity": 60.0,
        "refill_threshold_days": 5,
    }

    res = await client.post(f"/api/v1/elders/{elder_id}/medicines", headers=headers, json=payload)
    assert res.status_code == 201
    med_data = res.json()
    assert med_data["name"] == "Metformin"
    assert med_data["strength"] == "500 mg"
    assert med_data["days_remaining"] == 30  # 60 tablets / (2 tablets per day) = 30 days

    # Check doses generated for today
    doses_res = await client.get(f"/api/v1/elders/{elder_id}/doses?date={today}", headers=headers)
    assert doses_res.status_code == 200
    doses = doses_res.json()
    assert len(doses) == 2
    assert doses[0]["medicine_name"] == "Metformin"
    assert doses[0]["scheduled_time"].startswith("08:00")
    assert doses[1]["scheduled_time"].startswith("20:00")
    assert doses[0]["status"] == "scheduled"


@pytest.mark.asyncio
async def test_weekly_schedule_dose_generation(client: AsyncClient):
    token = await create_user_and_token(client, "med_owner2@example.com", "Med Owner 2")
    headers = {"Authorization": f"Bearer {token}"}
    creds = await create_elder_helper(client, token)
    elder_id = creds["elder_id"]

    # Start from next Monday to test exact 6 doses per week AC
    today = date.today()
    days_until_monday = (0 - today.weekday()) % 7
    if days_until_monday == 0:
        days_until_monday = 7
    next_monday = today + timedelta(days=days_until_monday)

    payload = {
        "name": "Methotrexate",
        "strength": "2.5 mg",
        "as_needed": False,
        "frequency": "weekly",
        "days_of_week": [1, 3, 5],  # Mon, Wed, Fri
        "times_of_day": ["08:00", "20:00"],
        "start_date": str(next_monday),
        "stock_quantity": 24.0,
    }

    res = await client.post(f"/api/v1/elders/{elder_id}/medicines", headers=headers, json=payload)
    assert res.status_code == 201

    # Over 7 days starting from next_monday (Mon to Sun):
    # Mon, Wed, Fri -> 3 days * 2 doses = exactly 6 doses per week!
    week_doses_count = 0
    for offset in range(7):
        target_d = next_monday + timedelta(days=offset)
        d_res = await client.get(f"/api/v1/elders/{elder_id}/doses?date={target_d}", headers=headers)
        week_doses_count += len(d_res.json())

    assert week_doses_count == 6


@pytest.mark.asyncio
async def test_as_needed_medicine_and_duplicate_warning(client: AsyncClient):
    token = await create_user_and_token(client, "med_owner3@example.com", "Med Owner 3")
    headers = {"Authorization": f"Bearer {token}"}
    creds = await create_elder_helper(client, token)
    elder_id = creds["elder_id"]

    # 1. As needed medicine
    payload = {
        "name": "Paracetamol",
        "strength": "650 mg",
        "as_needed": True,
        "instructions": "For fever over 100 F",
    }
    res = await client.post(f"/api/v1/elders/{elder_id}/medicines", headers=headers, json=payload)
    assert res.status_code == 201
    assert res.json()["as_needed"] is True
    assert res.json()["days_remaining"] is None  # As-needed has no days remaining

    # Doses for today should have 0 scheduled doses for paracetamol
    d_res = await client.get(f"/api/v1/elders/{elder_id}/doses", headers=headers)
    assert len(d_res.json()) == 0

    # 2. Duplicate check warning (MED-8)
    dup_res = await client.get(
        f"/api/v1/elders/{elder_id}/medicines/check-duplicate?name=paracetamol&strength=650 mg",
        headers=headers,
    )
    assert dup_res.status_code == 200
    assert dup_res.json()["is_duplicate"] is True
    assert "already exists" in dup_res.json()["warning"]


@pytest.mark.asyncio
async def test_schedule_edit_preserves_past_doses(client: AsyncClient):
    token = await create_user_and_token(client, "med_owner4@example.com", "Med Owner 4")
    headers = {"Authorization": f"Bearer {token}"}
    creds = await create_elder_helper(client, token)
    elder_id = creds["elder_id"]

    today = date.today()
    tomorrow = today + timedelta(days=1)

    # Initial: 08:00
    res = await client.post(
        f"/api/v1/elders/{elder_id}/medicines",
        headers=headers,
        json={
            "name": "Amlodipine",
            "strength": "5 mg",
            "frequency": "daily",
            "times_of_day": ["08:00"],
            "start_date": str(today),
        },
    )
    med_id = res.json()["id"]

    # Verify today has dose at 08:00
    today_doses = (await client.get(f"/api/v1/elders/{elder_id}/doses?date={today}", headers=headers)).json()
    assert len(today_doses) == 1
    assert today_doses[0]["scheduled_time"].startswith("08:00")

    # Edit schedule from tomorrow to 21:00 (MED-6)
    patch_res = await client.patch(
        f"/api/v1/elders/{elder_id}/medicines/{med_id}",
        headers=headers,
        json={
            "effective_from": str(tomorrow),
            "times_of_day": ["21:00"],
        },
    )
    assert patch_res.status_code == 200

    # Today's doses remain UNTOUCHED (08:00)
    today_after = (await client.get(f"/api/v1/elders/{elder_id}/doses?date={today}", headers=headers)).json()
    assert len(today_after) == 1
    assert today_after[0]["scheduled_time"].startswith("08:00")

    # Tomorrow's doses now have the new time (21:00)
    tomorrow_doses = (await client.get(f"/api/v1/elders/{elder_id}/doses?date={tomorrow}", headers=headers)).json()
    assert len(tomorrow_doses) == 1
    assert tomorrow_doses[0]["scheduled_time"].startswith("21:00")


@pytest.mark.asyncio
async def test_pause_resume_and_end_medicine(client: AsyncClient):
    token = await create_user_and_token(client, "med_owner5@example.com", "Med Owner 5")
    headers = {"Authorization": f"Bearer {token}"}
    creds = await create_elder_helper(client, token)
    elder_id = creds["elder_id"]

    today = date.today()
    res = await client.post(
        f"/api/v1/elders/{elder_id}/medicines",
        headers=headers,
        json={"name": "Atorvastatin", "frequency": "daily", "times_of_day": ["22:00"]},
    )
    med_id = res.json()["id"]

    # Pause medicine
    pause_res = await client.post(f"/api/v1/elders/{elder_id}/medicines/{med_id}/pause", headers=headers)
    assert pause_res.status_code == 200

    # Scheduled doses removed
    d_paused = (await client.get(f"/api/v1/elders/{elder_id}/doses?date={today}", headers=headers)).json()
    assert len(d_paused) == 0

    # Resume medicine
    resume_res = await client.post(f"/api/v1/elders/{elder_id}/medicines/{med_id}/resume", headers=headers)
    assert resume_res.status_code == 200

    # Scheduled doses restored
    d_resumed = (await client.get(f"/api/v1/elders/{elder_id}/doses?date={today}", headers=headers)).json()
    assert len(d_resumed) == 1

    # End medicine
    end_res = await client.post(f"/api/v1/elders/{elder_id}/medicines/{med_id}/end", headers=headers)
    assert end_res.status_code == 200
    med_ended = (await client.get(f"/api/v1/elders/{elder_id}/medicines/{med_id}", headers=headers)).json()
    assert med_ended["status"] == "ended"


@pytest.mark.asyncio
async def test_mark_dose_taken_and_10_min_undo(client: AsyncClient, db_session: AsyncSession):
    owner_token = await create_user_and_token(client, "caregiver_dose@example.com", "Caregiver User")
    owner_h = {"Authorization": f"Bearer {owner_token}"}
    creds = await create_elder_helper(client, owner_token)
    elder_id = creds["elder_id"]

    # Elder login
    elder_login_res = await client.post(
        "/api/v1/auth/elder/login",
        json={"access_code": creds["access_code"], "pin": creds["pin"]},
    )
    elder_token = elder_login_res.json()["access_token"]
    elder_h = {"Authorization": f"Bearer {elder_token}"}

    # Create medicine with initial stock of 10
    med_res = await client.post(
        f"/api/v1/elders/{elder_id}/medicines",
        headers=owner_h,
        json={
            "name": "Thyroxine",
            "dose_amount": 1.0,
            "stock_quantity": 10.0,
            "frequency": "daily",
            "times_of_day": ["07:00"],
        },
    )
    med_id = med_res.json()["id"]

    # Fetch today's dose as elder
    doses = (await client.get(f"/api/v1/elders/{elder_id}/doses", headers=elder_h)).json()
    assert len(doses) == 1
    dose_id = doses[0]["id"]
    assert doses[0]["status"] == "scheduled"
    assert doses[0]["can_undo"] is False

    # 1. Elder marks dose taken (Section 2.2: Elder own)
    take_res = await client.post(f"/api/v1/doses/{dose_id}/take", headers=elder_h)
    assert take_res.status_code == 200
    taken_data = take_res.json()
    assert taken_data["status"] == "taken"
    assert taken_data["can_undo"] is True

    # Check stock decreased from 10 to 9
    med_check = (await client.get(f"/api/v1/elders/{elder_id}/medicines/{med_id}", headers=owner_h)).json()
    assert Decimal(str(med_check["stock_quantity"])) == Decimal("9.0")

    # 2. Undo within 10 minutes (Section 8.3)
    undo_res = await client.post(f"/api/v1/doses/{dose_id}/undo", headers=elder_h)
    assert undo_res.status_code == 200
    undone_data = undo_res.json()
    assert undone_data["status"] == "scheduled"
    assert undone_data["can_undo"] is False

    # Check stock restored from 9 to 10
    med_check2 = (await client.get(f"/api/v1/elders/{elder_id}/medicines/{med_id}", headers=owner_h)).json()
    assert Decimal(str(med_check2["stock_quantity"])) == Decimal("10.0")

    # 3. Mark taken again, and simulate 11 minutes passing
    await client.post(f"/api/v1/doses/{dose_id}/take", headers=elder_h)

    # Manually backdate updated_at in DB by 11 minutes to test the 10-minute expiry
    from app.core.db import get_db
    from app.models.dose import DoseInstance
    from sqlalchemy import select

    # Update updated_at directly via db session
    stmt = select(DoseInstance).where(DoseInstance.id == uuid.UUID(dose_id))
    d_inst = (await db_session.execute(stmt)).scalar_one()
    d_inst.updated_at = datetime.utcnow() - timedelta(minutes=11)
    await db_session.commit()

    # Attempt undo after 10 minutes must fail with CANNOT_UNDO_EXPIRED
    expired_undo = await client.post(f"/api/v1/doses/{dose_id}/undo", headers=elder_h)
    assert expired_undo.status_code == 409
    assert expired_undo.json()["code"] == "CANNOT_UNDO_EXPIRED"


@pytest.mark.asyncio
async def test_caregiver_vs_family_permissions(client: AsyncClient):
    owner_token = await create_user_and_token(client, "owner_perm@example.com", "Owner Perm")
    family_token = await create_user_and_token(client, "family_only@example.com", "Family Only")

    owner_h = {"Authorization": f"Bearer {owner_token}"}
    family_h = {"Authorization": f"Bearer {family_token}"}

    creds = await create_elder_helper(client, owner_token)
    elder_id = creds["elder_id"]

    # Invite family member WITHOUT can_manage_medicines
    inv_res = await client.post(
        f"/api/v1/elders/{elder_id}/invites",
        headers=owner_h,
        json={"email": "family_only@example.com", "role": "family", "can_manage_medicines": False},
    )
    raw_token = inv_res.json()["invite_url"].split("/invites/")[1].split("/accept")[0]
    await client.post(f"/api/v1/invites/{raw_token}/accept", headers=family_h)

    # Family member cannot create medicine
    fail_create = await client.post(
        f"/api/v1/elders/{elder_id}/medicines",
        headers=family_h,
        json={"name": "Unauthorized Med"},
    )
    assert fail_create.status_code == 403

    # Owner creates medicine
    med_res = await client.post(
        f"/api/v1/elders/{elder_id}/medicines",
        headers=owner_h,
        json={"name": "Authorized Med", "frequency": "daily", "times_of_day": ["12:00"]},
    )
    dose_id = (await client.get(f"/api/v1/elders/{elder_id}/doses", headers=owner_h)).json()[0]["id"]

    # Family member cannot mark dose taken (Section 2.2: Family=No)
    fail_take = await client.post(f"/api/v1/doses/{dose_id}/take", headers=family_h)
    assert fail_take.status_code == 403

    # Family member cannot mark dose skipped (Section 2.2: Family=No)
    fail_skip = await client.post(f"/api/v1/doses/{dose_id}/skip", headers=family_h)
    assert fail_skip.status_code == 403

    # Owner (caregiver/owner) CAN mark dose skipped
    skip_res = await client.post(
        f"/api/v1/doses/{dose_id}/skip",
        headers=owner_h,
        json={"reason": "Elder was nauseous"},
    )
    assert skip_res.status_code == 200
    assert skip_res.json()["status"] == "skipped"
