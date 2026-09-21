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


@pytest.mark.asyncio
async def test_admin_schemas_data_lists_and_controls(async_client, db_session):
    a = await async_client.post("/auth/register", json={"email": "owner-sch@example.com", "password": "password123"})
    ha = {"Authorization": f"Bearer {a.json()['token']}"}
    created = await async_client.post(
        "/schemas",
        json={"name": "Escritura", "pydantic_schema": "class E(BaseModel):\n    x: int"},
        headers=ha,
    )
    sid = created.json()["id"]

    headers = await _admin(async_client, db_session)
    data = await async_client.get("/admin/schemas/data", headers=headers)
    assert data.status_code == 200
    rows = data.json()["schemas"]
    assert any(r["name"] == "Escritura" and r["owner_name"] == "owner-sch" for r in rows)

    pub = await async_client.put(f"/schemas/{sid}", json={"is_public": True}, headers=headers)
    assert pub.status_code == 200
    assert pub.json()["is_public"] is True

    dele = await async_client.delete(f"/schemas/{sid}", headers=headers)
    assert dele.status_code == 200
