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


@pytest.mark.asyncio
async def test_create_elder_and_day_close_validation(client: AsyncClient):
    token = await create_user_and_token(client, "owner_test@example.com", "Owner User")
    headers = {"Authorization": f"Bearer {token}"}

    # Day close time < 20:00 must fail validation (Section 4.2 / Section 15)
    invalid_payload = {
        "full_name": "Ramesh Gupta",
        "day_close_time": "18:30",
    }
    res_invalid = await client.post("/api/v1/elders", headers=headers, json=invalid_payload)
    assert res_invalid.status_code == 422

    # Valid elder creation
    valid_payload = {
        "full_name": "Ramesh Gupta",
        "preferred_name": "Babuji",
        "language": "hi",
        "timezone": "Asia/Kolkata",
        "day_close_time": "23:59",
        "text_size": 1,
    }
    res_valid = await client.post("/api/v1/elders", headers=headers, json=valid_payload)
    assert res_valid.status_code == 201
    creds = res_valid.json()
    assert "elder_id" in creds
    assert creds["access_code"].startswith("AIRA-")
    assert len(creds["pin"]) == 4
    assert creds["pin"].isdigit()
    assert "qr_url" in creds
    assert "token=" in creds["qr_url"]


@pytest.mark.asyncio
async def test_list_and_get_elder(client: AsyncClient):
    token1 = await create_user_and_token(client, "user1@example.com", "User One")
    token2 = await create_user_and_token(client, "user2@example.com", "User Two")

    h1 = {"Authorization": f"Bearer {token1}"}
    h2 = {"Authorization": f"Bearer {token2}"}

    # Create elder for user 1
    create_res = await client.post(
        "/api/v1/elders",
        headers=h1,
        json={"full_name": "Sita Devi", "preferred_name": "Mataji", "day_close_time": "22:00"},
    )
    elder_id = create_res.json()["elder_id"]

    # User 1 should see the elder
    list_res1 = await client.get("/api/v1/elders", headers=h1)
    assert list_res1.status_code == 200
    elders1 = list_res1.json()
    assert len(elders1) == 1
    assert elders1[0]["full_name"] == "Sita Devi"
    assert elders1[0]["is_owner"] is True
    assert elders1[0]["can_manage_medicines"] is True

    # User 2 should NOT see the elder
    list_res2 = await client.get("/api/v1/elders", headers=h2)
    assert list_res2.status_code == 200
    assert len(list_res2.json()) == 0

    # User 2 forbidden from direct GET
    get_res2 = await client.get(f"/api/v1/elders/{elder_id}", headers=h2)
    assert get_res2.status_code == 403

    # User 1 allowed
    get_res1 = await client.get(f"/api/v1/elders/{elder_id}", headers=h1)
    assert get_res1.status_code == 200
    assert get_res1.json()["id"] == elder_id


@pytest.mark.asyncio
async def test_update_and_archive_elder(client: AsyncClient):
    token = await create_user_and_token(client, "updater@example.com", "Updater")
    headers = {"Authorization": f"Bearer {token}"}

    create_res = await client.post(
        "/api/v1/elders",
        headers=headers,
        json={"full_name": "Original Elder", "day_close_time": "23:59"},
    )
    elder_id = create_res.json()["elder_id"]

    # Update profile
    patch_res = await client.patch(
        f"/api/v1/elders/{elder_id}",
        headers=headers,
        json={"preferred_name": "Dada", "text_size": 2},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["preferred_name"] == "Dada"
    assert patch_res.json()["text_size"] == 2

    # Archive profile
    archive_res = await client.post(f"/api/v1/elders/{elder_id}/archive", headers=headers)
    assert archive_res.status_code == 200

    # Archived elder no longer appears in list
    list_res = await client.get("/api/v1/elders", headers=headers)
    assert len(list_res.json()) == 0


@pytest.mark.asyncio
async def test_elder_pin_login_and_lockout(client: AsyncClient):
    token = await create_user_and_token(client, "guardian@example.com", "Guardian")
    headers = {"Authorization": f"Bearer {token}"}

    create_res = await client.post(
        "/api/v1/elders",
        headers=headers,
        json={"full_name": "Devi Prasad", "day_close_time": "21:00"},
    )
    creds = create_res.json()
    code = creds["access_code"]
    pin = creds["pin"]

    # 1. Successful Elder Login
    login_res = await client.post(
        "/api/v1/auth/elder/login",
        json={"access_code": code, "pin": pin, "device_label": "Tablet-Hall"},
    )
    assert login_res.status_code == 200
    assert "access_token" in login_res.json()
    assert "access_token" in login_res.cookies

    # 2. Failed attempts (4 failures)
    for _ in range(4):
        fail_res = await client.post(
            "/api/v1/auth/elder/login",
            json={"access_code": code, "pin": "0000"},
        )
        assert fail_res.status_code == 401
        assert fail_res.json()["code"] == "INVALID_CREDENTIALS"

    # 3. 5th failure triggers 15-minute lockout (AUTH-4)
    lock_res = await client.post(
        "/api/v1/auth/elder/login",
        json={"access_code": code, "pin": "0000"},
    )
    assert lock_res.status_code == 401
    assert lock_res.json()["code"] == "ELDER_LOCKED"

    # 4. Even with the CORRECT PIN, access is locked for 15 minutes
    locked_attempt = await client.post(
        "/api/v1/auth/elder/login",
        json={"access_code": code, "pin": pin},
    )
    assert locked_attempt.status_code == 401
    assert locked_attempt.json()["code"] == "ELDER_LOCKED"


@pytest.mark.asyncio
async def test_elder_qr_login_and_session_revocation(client: AsyncClient):
    token = await create_user_and_token(client, "qr_owner@example.com", "QR Owner")
    headers = {"Authorization": f"Bearer {token}"}

    create_res = await client.post(
        "/api/v1/elders",
        headers=headers,
        json={"full_name": "Krishna Murthy", "day_close_time": "22:00"},
    )
    creds = create_res.json()
    elder_id = creds["elder_id"]
    qr_token = creds["qr_token"]

    # QR Login
    qr_res = await client.post(
        "/api/v1/auth/elder/qr",
        json={"token": qr_token, "device_label": "Living Room Screen"},
    )
    assert qr_res.status_code == 200
    assert "access_token" in qr_res.json()

    # Invalid QR token fails
    invalid_qr = await client.post(
        "/api/v1/auth/elder/qr",
        json={"token": "completely_bogus_token"},
    )
    assert invalid_qr.status_code == 401
    assert invalid_qr.json()["code"] == "INVALID_QR_TOKEN"

    # Check active sessions
    sessions_res = await client.get(f"/api/v1/elders/{elder_id}/sessions", headers=headers)
    assert sessions_res.status_code == 200
    sessions = sessions_res.json()
    assert len(sessions) >= 1
    session_id = sessions[0]["id"]

    # Owner regenerates credentials (AUTH-4: revokes old sessions)
    regen_res = await client.post(f"/api/v1/elders/{elder_id}/access/regenerate", headers=headers)
    assert regen_res.status_code == 200
    new_creds = regen_res.json()
    assert new_creds["access_code"] != creds["access_code"]

    # Old sessions should now be revoked (empty active sessions)
    post_sessions = await client.get(f"/api/v1/elders/{elder_id}/sessions", headers=headers)
    assert len(post_sessions.json()) == 0

    # Old QR token no longer works
    old_qr_retry = await client.post(
        "/api/v1/auth/elder/qr",
        json={"token": qr_token},
    )
    assert old_qr_retry.status_code == 401


@pytest.mark.asyncio
async def test_care_team_and_invites(client: AsyncClient):
    owner_token = await create_user_and_token(client, "team_owner@example.com", "Team Owner")
    member_token = await create_user_and_token(client, "caregiver_invitee@example.com", "Caregiver Invitee")

    owner_h = {"Authorization": f"Bearer {owner_token}"}
    member_h = {"Authorization": f"Bearer {member_token}"}

    create_res = await client.post(
        "/api/v1/elders",
        headers=owner_h,
        json={"full_name": "Ananya Roy", "day_close_time": "23:00"},
    )
    elder_id = create_res.json()["elder_id"]

    # 1. Invite caregiver
    invite_payload = {
        "email": "caregiver_invitee@example.com",
        "role": "caregiver",
        "can_manage_medicines": True,
    }
    invite_res = await client.post(
        f"/api/v1/elders/{elder_id}/invites",
        headers=owner_h,
        json=invite_payload,
    )
    assert invite_res.status_code == 201
    invite_data = invite_res.json()
    invite_url = invite_data["invite_url"]
    raw_token = invite_url.split("/invites/")[1].split("/accept")[0]

    # 2. Accept Invite as the member
    accept_res = await client.post(f"/api/v1/invites/{raw_token}/accept", headers=member_h)
    assert accept_res.status_code == 200

    # 3. Check Team List
    team_res = await client.get(f"/api/v1/elders/{elder_id}/team", headers=owner_h)
    assert team_res.status_code == 200
    team = team_res.json()
    assert len(team) == 2
    owner_entry = next(m for m in team if m["is_owner"] is True)
    cg_entry = next(m for m in team if m["is_owner"] is False)
    assert cg_entry["email"] == "caregiver_invitee@example.com"
    assert cg_entry["role"] == "caregiver"
    assert cg_entry["can_manage_medicines"] is True

    # 4. Non-owner cannot remove anyone
    fail_remove = await client.delete(
        f"/api/v1/elders/{elder_id}/team/{owner_entry['user_id']}",
        headers=member_h,
    )
    assert fail_remove.status_code == 403

    # 5. Owner cannot remove the last owner (ELD-3)
    last_owner_fail = await client.delete(
        f"/api/v1/elders/{elder_id}/team/{owner_entry['user_id']}",
        headers=owner_h,
    )
    assert last_owner_fail.status_code == 409
    assert last_owner_fail.json()["code"] == "LAST_OWNER_CANNOT_BE_REMOVED"

    # 6. Owner can remove caregiver
    remove_res = await client.delete(
        f"/api/v1/elders/{elder_id}/team/{cg_entry['user_id']}",
        headers=owner_h,
    )
    assert remove_res.status_code == 200

    # Verify caregiver is removed
    team_after = await client.get(f"/api/v1/elders/{elder_id}/team", headers=owner_h)
    assert len(team_after.json()) == 1
