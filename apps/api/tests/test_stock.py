import uuid
from decimal import Decimal
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
        json={"full_name": "Kailash Nath", "day_close_time": "23:59"},
    )
    return res.json()


@pytest.mark.asyncio
async def test_refill_and_ledger_history(client: AsyncClient):
    token = await create_user_and_token(client, "stock_owner@example.com", "Stock Owner")
    headers = {"Authorization": f"Bearer {token}"}
    creds = await create_elder_helper(client, token)
    elder_id = creds["elder_id"]

    # Create medicine with initial stock of 10
    med_res = await client.post(
        f"/api/v1/elders/{elder_id}/medicines",
        headers=headers,
        json={
            "name": "Glimepiride",
            "dose_amount": 1.0,
            "stock_quantity": 10.0,
            "refill_threshold_days": 5,
            "frequency": "daily",
            "times_of_day": ["08:00"],
        },
    )
    med_id = med_res.json()["id"]

    # 1. Record refill of 30 units (STK-2, STK-5)
    refill_res = await client.post(
        f"/api/v1/elders/{elder_id}/medicines/{med_id}/refill",
        headers=headers,
        json={"quantity": 30.0, "note": "Bought 1 strip from Apollo Pharmacy"},
    )
    assert refill_res.status_code == 200
    updated_med = refill_res.json()
    assert Decimal(str(updated_med["stock_quantity"])) == Decimal("40.0")
    assert updated_med["days_remaining"] == 40

    # 2. Check stock event ledger (STK-2)
    events_res = await client.get(
        f"/api/v1/elders/{elder_id}/medicines/{med_id}/stock-events",
        headers=headers,
    )
    assert events_res.status_code == 200
    events = events_res.json()
    # At least initial_stock + refill
    assert len(events) >= 2
    latest_event = events[0]
    assert latest_event["reason"] == "refill"
    assert Decimal(str(latest_event["delta"])) == Decimal("30.0")
    assert "Apollo Pharmacy" in latest_event["note"]


@pytest.mark.asyncio
async def test_manual_stock_adjustment(client: AsyncClient):
    token = await create_user_and_token(client, "adjust_owner@example.com", "Adjust Owner")
    headers = {"Authorization": f"Bearer {token}"}
    creds = await create_elder_helper(client, token)
    elder_id = creds["elder_id"]

    med_res = await client.post(
        f"/api/v1/elders/{elder_id}/medicines",
        headers=headers,
        json={"name": "Pantoprazole", "stock_quantity": 20.0, "frequency": "daily", "times_of_day": ["07:30"]},
    )
    med_id = med_res.json()["id"]

    # 1. Adjust to exact new_quantity
    adj_res = await client.post(
        f"/api/v1/elders/{elder_id}/medicines/{med_id}/stock-adjust",
        headers=headers,
        json={"new_quantity": 25.0, "note": "Found 5 extra tablets in drawer"},
    )
    assert adj_res.status_code == 200
    assert Decimal(str(adj_res.json()["stock_quantity"])) == Decimal("25.0")

    # 2. Adjust using negative delta
    delta_res = await client.post(
        f"/api/v1/elders/{elder_id}/medicines/{med_id}/stock-adjust",
        headers=headers,
        json={"delta": -3.0, "note": "Dropped 3 tablets"},
    )
    assert delta_res.status_code == 200
    assert Decimal(str(delta_res.json()["stock_quantity"])) == Decimal("22.0")


@pytest.mark.asyncio
async def test_stock_ledger_tracks_doses_and_undo(client: AsyncClient):
    token = await create_user_and_token(client, "dose_ledger_owner@example.com", "Dose Ledger Owner")
    headers = {"Authorization": f"Bearer {token}"}
    creds = await create_elder_helper(client, token)
    elder_id = creds["elder_id"]

    med_res = await client.post(
        f"/api/v1/elders/{elder_id}/medicines",
        headers=headers,
        json={"name": "Losartan", "dose_amount": 2.0, "stock_quantity": 20.0, "frequency": "daily", "times_of_day": ["09:00"]},
    )
    med_id = med_res.json()["id"]

    # Fetch today's dose
    doses = (await client.get(f"/api/v1/elders/{elder_id}/doses", headers=headers)).json()
    dose_id = doses[0]["id"]

    # 1. Caregiver marks dose taken on behalf of elder
    await client.post(f"/api/v1/doses/{dose_id}/take", headers=headers)

    # Check stock decreased by dose_amount (2.0) -> 18.0
    med_after_take = (await client.get(f"/api/v1/elders/{elder_id}/medicines/{med_id}", headers=headers)).json()
    assert Decimal(str(med_after_take["stock_quantity"])) == Decimal("18.0")

    # 2. Caregiver undos dose taken
    await client.post(f"/api/v1/doses/{dose_id}/undo", headers=headers)

    # Check stock restored to 20.0
    med_after_undo = (await client.get(f"/api/v1/elders/{elder_id}/medicines/{med_id}", headers=headers)).json()
    assert Decimal(str(med_after_undo["stock_quantity"])) == Decimal("20.0")

    # Check ledger history contains dose_taken and dose_undo
    events = (await client.get(f"/api/v1/elders/{elder_id}/medicines/{med_id}/stock-events", headers=headers)).json()
    reasons = [ev["reason"] for ev in events]
    assert "dose_taken" in reasons
    assert "dose_undo" in reasons
