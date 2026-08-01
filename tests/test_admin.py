import pytest
from fastapi import HTTPException
from unittest.mock import AsyncMock, MagicMock, patch

from app.auth import get_admin_user


@pytest.mark.asyncio
async def test_get_admin_user_allows_admin():
    mock_user = MagicMock()
    mock_user.role = "admin"
    result = await get_admin_user(mock_user)
    assert result == mock_user


@pytest.mark.asyncio
async def test_get_admin_user_rejects_regular():
    mock_user = MagicMock()
    mock_user.role = "user"
    with pytest.raises(HTTPException) as exc:
        await get_admin_user(mock_user)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_admin_users_list(async_client):
    # Register an admin user first
    reg = await async_client.post("/auth/register", json={
        "email": "admin-test@example.com",
        "password": "password123",
    })
    assert reg.status_code == 200
    token = reg.json()["token"]

    # Promote to admin via DB (directly, since only admin can promote)
    from app.database import async_session
    from app.models import User
    async with async_session() as s:
        user = await s.execute(__import__("sqlalchemy").select(User).where(User.email == "admin-test@example.com"))
        u = user.scalar_one()
        u.role = "admin"
        await s.commit()

    # Now access /admin/users/data with admin token
    resp = await async_client.get("/admin/users/data", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "users" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_admin_users_rejects_non_admin(async_client):
    # Register a regular user
    reg = await async_client.post("/auth/register", json={
        "email": "regular@example.com",
        "password": "password123",
    })
    assert reg.status_code == 200
    token = reg.json()["token"]

    # Access /admin/users with regular user token
    resp = await async_client.get("/admin/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_toggle_user_status(async_client):
    # Register admin and another user
    await async_client.post("/auth/register", json={"email": "admin2@example.com", "password": "password123"})
    reg2 = await async_client.post("/auth/register", json={"email": "target@example.com", "password": "password123"})

    # Promote admin
    from app.database import async_session
    from app.models import User
    async with async_session() as s:
        u = (await s.execute(__import__("sqlalchemy").select(User).where(User.email == "admin2@example.com"))).scalar_one()
        u.role = "admin"
        await s.commit()

    # Login as admin
    login = await async_client.post("/auth/login", json={"email": "admin2@example.com", "password": "password123"})
    token = login.json()["token"]

    target_id = reg2.json()["user"]["id"]

    # Toggle target user off
    resp = await async_client.post(
        f"/admin/users/{target_id}/toggle-status",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


async def _make_admin(client, email):
    await client.post("/auth/register", json={"email": email, "password": "password123"})
    from app.database import async_session
    from app.models import User
    async with async_session() as s:
        u = (await s.execute(__import__("sqlalchemy").select(User).where(User.email == email))).scalar_one()
        u.role = "admin"
        await s.commit()
    login = await client.post("/auth/login", json={"email": email, "password": "password123"})
    return login.json()["token"]


@pytest.mark.asyncio
async def test_admin_create_user(async_client):
    token = await _make_admin(async_client, "boss@example.com")
    resp = await async_client.post(
        "/admin/users",
        json={"email": "newbie@example.com", "password": "password123", "display_name": "Newbie"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "newbie@example.com"
    assert data["role"] == "user"

    listing = await async_client.get("/admin/users/data", headers={"Authorization": f"Bearer {token}"})
    emails = [u["email"] for u in listing.json()["users"]]
    assert "newbie@example.com" in emails
