import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_and_ready(client: AsyncClient):
    res = await client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

    res_ready = await client.get("/ready")
    assert res_ready.status_code == 200
    assert res_ready.json()["status"] == "ready"


@pytest.mark.asyncio
async def test_user_registration(client: AsyncClient):
    payload = {
        "email": "priya@example.com",
        "password": "Password1234!",
        "full_name": "Priya Sharma",
        "preferred_language": "hi",
        "timezone": "Asia/Kolkata",
    }
    res = await client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["email"] == "priya@example.com"
    assert data["full_name"] == "Priya Sharma"
    assert data["preferred_language"] == "hi"
    assert data["is_verified"] is True

    # Duplicate registration should return 409 Conflict
    res_dup = await client.post("/api/v1/auth/register", json=payload)
    assert res_dup.status_code == 409
    assert res_dup.json()["code"] == "EMAIL_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_email_verification_flow(client: AsyncClient):
    # Temporarily set APP_ENV to prod-like to test verification requirement
    from app.config import settings
    settings.APP_ENV = "production"

    res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "unverified@example.com",
            "password": "Password1234!",
            "full_name": "Unverified User",
        },
    )
    assert res.status_code == 201
    assert res.json()["is_verified"] is False

    # Attempt login before verification fails
    login_fail = await client.post(
        "/api/v1/auth/login",
        json={"email": "unverified@example.com", "password": "Password1234!"},
    )
    assert login_fail.status_code == 401
    assert login_fail.json()["code"] == "EMAIL_NOT_VERIFIED"

    settings.APP_ENV = "test"


@pytest.mark.asyncio
async def test_registration_password_min_length(client: AsyncClient):
    payload = {
        "email": "short@example.com",
        "password": "short",
        "full_name": "Short Pass",
    }
    res = await client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 422
    assert res.json()["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_login_and_cookie_session(client: AsyncClient):
    # Register first
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "login_test@example.com",
            "password": "ValidPassword123!",
            "full_name": "Login Test User",
        },
    )

    # Login
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "login_test@example.com", "password": "ValidPassword123!"},
    )
    assert login_res.status_code == 200
    assert "access_token" in login_res.json()
    assert "access_token" in login_res.cookies
    assert "refresh_token" in login_res.cookies

    # Wrong password fails
    bad_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "login_test@example.com", "password": "WrongPassword!"},
    )
    assert bad_login.status_code == 401
    assert bad_login.json()["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_refresh_token_rotation_and_reuse_revocation(client: AsyncClient):
    # Register and login
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "refresh_test@example.com",
            "password": "StrongPassword999!",
            "full_name": "Refresh User",
        },
    )

    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "refresh_test@example.com", "password": "StrongPassword999!"},
    )
    initial_refresh_token = login_res.cookies["refresh_token"]

    # 1. Valid Refresh
    refresh_res1 = await client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": initial_refresh_token},
    )
    assert refresh_res1.status_code == 200
    new_refresh_token = refresh_res1.cookies["refresh_token"]
    assert new_refresh_token != initial_refresh_token

    # 2. Reuse Detection: Present the OLD already-revoked refresh token!
    reuse_res = await client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": initial_refresh_token},
    )
    # Must fail with TOKEN_FAMILY_REVOKED
    assert reuse_res.status_code == 401
    assert reuse_res.json()["code"] == "TOKEN_FAMILY_REVOKED"

    # 3. Even the new token should now be invalidated because the family was revoked!
    refresh_res3 = await client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": new_refresh_token},
    )
    assert refresh_res3.status_code == 401


@pytest.mark.asyncio
async def test_current_user_profile_and_update(client: AsyncClient):
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "me_test@example.com",
            "password": "StrongPassword999!",
            "full_name": "Original Name",
            "preferred_language": "en",
        },
    )
    user_id = reg_res.json()["id"]

    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "me_test@example.com", "password": "StrongPassword999!"},
    )
    token = login_res.json()["access_token"]

    # GET /me with Bearer token
    me_res = await client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["full_name"] == "Original Name"

    # PATCH /me
    patch_res = await client.patch(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"full_name": "Updated Name", "preferred_language": "hi"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["full_name"] == "Updated Name"
    assert patch_res.json()["preferred_language"] == "hi"


@pytest.mark.asyncio
async def test_logout(client: AsyncClient):
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "logout_test@example.com",
            "password": "StrongPassword999!",
            "full_name": "Logout User",
        },
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "logout_test@example.com", "password": "StrongPassword999!"},
    )
    ref_token = login_res.cookies["refresh_token"]

    logout_res = await client.post(
        "/api/v1/auth/logout",
        cookies={"refresh_token": ref_token},
    )
    assert logout_res.status_code == 200
