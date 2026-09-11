import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.models import LLMConnection, ModelRegistry, User, UserModelAccess
from app.providers.base import ModelInfo


async def _admin(async_client, db_session):
    reg = await async_client.post("/auth/register", json={
        "email": "admin-models@example.com",
        "password": "password123",
    })
    result = await db_session.execute(select(User).where(User.email == "admin-models@example.com"))
    user = result.scalar_one()
    user.role = "admin"
    await db_session.commit()
    return reg


async def _user(async_client, db_session, email="plain@example.com"):
    await async_client.post("/auth/register", json={"email": email, "password": "password123"})


def _conn(db_session, name="conn1", provider="ollama"):
    conn = LLMConnection(name=name, provider=provider, config={}, secrets="{}")
    db_session.add(conn)
    return conn


async def _reg(db_session, conn, name, **kw):
    reg = ModelRegistry(connection_id=conn.id, model_name=name, **kw)
    db_session.add(reg)
    return reg


@pytest.mark.asyncio
async def test_admin_models_page_served(async_client, db_session):
    await _admin(async_client, db_session)
    resp = await async_client.get("/admin/models")
    assert resp.status_code == 200
    assert "model" in resp.text.lower()


@pytest.mark.asyncio
async def test_admin_models_data_lists_models(async_client, db_session):
    await _admin(async_client, db_session)
    conn = _conn(db_session)
    await db_session.flush()
    await _reg(db_session, conn, "alpha", enabled=True)
    await db_session.commit()

    resp = await async_client.get("/admin/models/data")
    assert resp.status_code == 200
    rows = resp.json()["models"]
    assert len(rows) == 1
    assert rows[0]["model_name"] == "alpha"
    assert rows[0]["connection"] == "conn1"


@pytest.mark.asyncio
async def test_admin_models_data_hides_disabled_by_default(async_client, db_session):
    await _admin(async_client, db_session)
    conn = _conn(db_session)
    await db_session.flush()
    await _reg(db_session, conn, "on", enabled=True)
    await _reg(db_session, conn, "off", enabled=False)
    await db_session.commit()

    resp = await async_client.get("/admin/models/data")
    names = [r["model_name"] for r in resp.json()["models"]]
    assert "on" in names
    assert "off" not in names

    resp2 = await async_client.get("/admin/models/data?include_hidden=1")
    names2 = [r["model_name"] for r in resp2.json()["models"]]
    assert "off" in names2


@pytest.mark.asyncio
async def test_admin_models_requires_admin(async_client, db_session):
    await _user(async_client, db_session)
    resp = await async_client.get("/admin/models/data")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_models_requires_auth(async_client):
    resp = await async_client.get("/admin/models/data")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_admin_models_refresh_syncs_registry(async_client, db_session):
    await _admin(async_client, db_session)
    fake = type("Fake", (), {"list_models": lambda self: [ModelInfo(id="ollama/x", provider="ollama", model_name="x", capabilities=["text"])]})()
    with patch("app.main._build_provider", return_value=fake):
        resp = await async_client.post("/admin/models/refresh")
    assert resp.status_code == 200
    regs = (await db_session.execute(select(ModelRegistry))).scalars().all()
    assert any(r.model_name == "x" for r in regs)


@pytest.mark.asyncio
async def test_admin_models_patch_updates_and_sets_default(async_client, db_session):
    await _admin(async_client, db_session)
    conn = _conn(db_session)
    await db_session.flush()
    a = await _reg(db_session, conn, "a")
    b = await _reg(db_session, conn, "b")
    await db_session.commit()

    resp = await async_client.patch(
        f"/admin/models/{a.id}",
        json={"display_name": "Alpha", "price_input_usd": 1.0, "is_default": True},
    )
    assert resp.status_code == 200
    await db_session.refresh(a)
    assert a.display_name == "Alpha"
    assert a.price_input_usd == 1.0
    assert a.is_default is True

    resp = await async_client.patch(f"/admin/models/{b.id}", json={"is_default": True})
    assert resp.status_code == 200
    await db_session.refresh(a)
    await db_session.refresh(b)
    assert b.is_default is True
    assert a.is_default is False


@pytest.mark.asyncio
async def test_admin_user_models_grants(async_client, db_session):
    await _user(async_client, db_session)
    await _admin(async_client, db_session)
    result = await db_session.execute(select(User).where(User.email == "plain@example.com"))
    target = result.scalar_one()
    conn = _conn(db_session)
    await db_session.flush()
    a = await _reg(db_session, conn, "a")
    b = await _reg(db_session, conn, "b")
    await db_session.commit()

    resp = await async_client.put(
        f"/admin/users/{target.id}/models",
        json={"grants": [
            {"model_id": str(a.id), "access": "allow"},
            {"model_id": str(b.id), "access": "deny"},
        ]},
    )
    assert resp.status_code == 200

    resp = await async_client.get(f"/admin/users/{target.id}/models")
    grants = {g["model_name"]: g["access"] for g in resp.json()["grants"]}
    assert grants == {"a": "allow", "b": "deny"}

    resp = await async_client.put(
        f"/admin/users/{target.id}/models",
        json={"grants": [{"model_id": str(a.id), "access": "default"}]},
    )
    assert resp.status_code == 200
    resp = await async_client.get(f"/admin/users/{target.id}/models")
    grants = [g["model_name"] for g in resp.json()["grants"]]
    assert grants == ["b"]