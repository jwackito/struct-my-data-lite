import pytest
from sqlalchemy import select

from app.models import User


async def _admin(async_client, db_session, email="adm@example.com"):
    reg = await async_client.post("/auth/register", json={"email": email, "password": "password123"})
    user = (await db_session.execute(select(User).where(User.email == email))).scalar_one()
    user.role = "admin"
    await db_session.commit()
    return {"Authorization": f"Bearer {reg.json()['token']}"}


@pytest.mark.asyncio
async def test_admin_schemas_data_requires_admin(async_client):
    reg = await async_client.post("/auth/register", json={"email": "plain-sch@example.com", "password": "password123"})
    headers = {"Authorization": f"Bearer {reg.json()['token']}"}
    resp = await async_client.get("/admin/schemas/data", headers=headers)
    assert resp.status_code == 403
