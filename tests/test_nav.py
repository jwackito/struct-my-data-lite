import pytest
from sqlalchemy import select

from app.models import User


@pytest.mark.asyncio
async def test_nav_shows_user_name_and_links(async_client):
    await async_client.post("/auth/register", json={
        "email": "nav-user@example.com",
        "password": "password123",
        "display_name": "Nav Tester",
    })
    resp = await async_client.get("/")
    assert resp.status_code == 200
    html = resp.text
    assert 'id="user-name"' in html
    assert "Nav Tester" in html
    assert 'href="/ui/batches"' in html
    assert 'href="/usage"' in html
    assert 'href="/ui/settings"' in html
    assert 'class="active"' in html


@pytest.mark.asyncio
async def test_nav_admin_links(async_client, db_session):
    await async_client.post("/auth/register", json={"email": "nav-admin@example.com", "password": "password123"})
    user = (await db_session.execute(select(User).where(User.email == "nav-admin@example.com"))).scalar_one()
    user.role = "admin"
    await db_session.commit()

    resp = await async_client.get("/")
    assert resp.status_code == 200
    html = resp.text
    assert 'href="/admin/usage"' in html
    assert 'href="/admin/users"' in html
    assert 'href="/admin/models"' in html
    assert 'href="/admin/schemas"' in html


@pytest.mark.asyncio
async def test_login_has_no_nav(async_client):
    resp = await async_client.get("/login")
    assert resp.status_code == 200
    assert 'id="user-name"' not in resp.text
    assert "/auth/logout" not in resp.text
