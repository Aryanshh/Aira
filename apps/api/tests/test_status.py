import uuid
from datetime import date, datetime, timedelta
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
        json={"full_name": "Radha Rani", "preferred_name": "Dadi", "day_close_time": "23:59"},
    )
    return res.json()


@pytest.mark.asyncio
async def test_day_status_aggregation_and_states(client: AsyncClient):
    token = await create_user_and_token(client, "status_owner1@example.com", "Status Owner 1")
    headers = {"Authorization": f"Bearer {token}"}
    creds = await create_elder_helper(client, token)
    elder_id = creds["elder_id"]

    today = date.today()

    # Create medicine with 2 daily doses
    await client.post(
        f"/api/v1/elders/{elder_id}/medicines",
        headers=headers,
        json={
            "name": "Metoprolol",
            "dose_amount": 1.0,
            "frequency": "daily",
            "times_of_day": ["08:00", "20:00"],
            "start_date": str(today),
        },
    )

    # 1. Initially 0/2 taken -> in_progress (0%)
    status_res1 = await client.get(f"/api/v1/elders/{elder_id}/status/day?date={today}", headers=headers)
    assert status_res1.status_code == 200
    s1 = status_res1.json()
    assert s1["total_scheduled"] == 2
    assert s1["taken_count"] == 0
    assert s1["adherence_pct"] == 0
    assert s1["state"] == "in_progress"

    # Fetch today's doses
    doses = (await client.get(f"/api/v1/elders/{elder_id}/doses?date={today}", headers=headers)).json()
    assert len(doses) == 2

    # 2. Mark first dose taken -> in_progress (50%)
    await client.post(f"/api/v1/doses/{doses[0]['id']}/take", headers=headers)
    status_res2 = await client.get(f"/api/v1/elders/{elder_id}/status/day?date={today}", headers=headers)
    s2 = status_res2.json()
    assert s2["taken_count"] == 1
    assert s2["adherence_pct"] == 50
    assert s2["state"] == "in_progress"

    # 3. Mark second dose taken -> all_taken (100%)
    await client.post(f"/api/v1/doses/{doses[1]['id']}/take", headers=headers)
    status_res3 = await client.get(f"/api/v1/elders/{elder_id}/status/day?date={today}", headers=headers)
    s3 = status_res3.json()
    assert s3["taken_count"] == 2
    assert s3["adherence_pct"] == 100
    assert s3["state"] == "all_taken"


@pytest.mark.asyncio
async def test_day_closing_marks_scheduled_as_missed(client: AsyncClient):
    token = await create_user_and_token(client, "close_owner@example.com", "Close Owner")
    headers = {"Authorization": f"Bearer {token}"}
    creds = await create_elder_helper(client, token)
    elder_id = creds["elder_id"]

    today = date.today()

    # Create medicine with 2 daily doses
    await client.post(
        f"/api/v1/elders/{elder_id}/medicines",
        headers=headers,
        json={
            "name": "Enalapril",
            "frequency": "daily",
            "times_of_day": ["09:00", "21:00"],
            "start_date": str(today),
        },
    )

    doses = (await client.get(f"/api/v1/elders/{elder_id}/doses?date={today}", headers=headers)).json()
    # Mark first dose taken, leave second dose scheduled
    await client.post(f"/api/v1/doses/{doses[0]['id']}/take", headers=headers)

    # Trigger day closure for today
    close_res = await client.post(f"/api/v1/elders/{elder_id}/close-day?date={today}", headers=headers)
    assert close_res.status_code == 200
    c_data = close_res.json()
    assert c_data["doses_marked_missed"] == 1
    assert c_data["already_closed"] is False

    # Second call is idempotent: already_closed = True
    dup_close = await client.post(f"/api/v1/elders/{elder_id}/close-day?date={today}", headers=headers)
    assert dup_close.status_code == 200
    assert dup_close.json()["already_closed"] is True

    # Check day summary now reflects missed status (STA-1, STA-4)
    summary_after = (await client.get(f"/api/v1/elders/{elder_id}/status/day?date={today}", headers=headers)).json()
    assert summary_after["state"] == "has_missed"
    assert summary_after["missed_count"] == 1
    assert summary_after["adherence_pct"] == 50
    assert "Enalapril" in summary_after["missed_medicine_names"]


@pytest.mark.asyncio
async def test_week_and_month_status_summaries(client: AsyncClient):
    token = await create_user_and_token(client, "week_owner@example.com", "Week Owner")
    headers = {"Authorization": f"Bearer {token}"}
    creds = await create_elder_helper(client, token)
    elder_id = creds["elder_id"]

    today = date.today()
    week_start = today - timedelta(days=today.weekday())

    # Create medicine
    await client.post(
        f"/api/v1/elders/{elder_id}/medicines",
        headers=headers,
        json={"name": "Aspirin", "frequency": "daily", "times_of_day": ["08:00"], "start_date": str(week_start)},
    )

    # 1. Week Summary
    week_res = await client.get(f"/api/v1/elders/{elder_id}/status/week?week_start={week_start}", headers=headers)
    assert week_res.status_code == 200
    w_data = week_res.json()
    assert len(w_data["days"]) == 7
    assert "overall_adherence_pct" in w_data
    assert "missed_highlights" in w_data

    # 2. Month Summary
    month_res = await client.get(
        f"/api/v1/elders/{elder_id}/status/month?year={today.year}&month={today.month}",
        headers=headers,
    )
    assert month_res.status_code == 200
    m_data = month_res.json()
    assert m_data["year"] == today.year
    assert m_data["month"] == today.month
    assert len(m_data["days"]) >= 28


@pytest.mark.asyncio
async def test_worker_day_closure_cycle(client: AsyncClient, db_session: AsyncSession):
    from app.services.status_service import StatusService

    service = StatusService(db_session)
    closed = await service.run_worker_day_closure_cycle()
    assert isinstance(closed, int)
