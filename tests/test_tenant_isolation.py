import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.models import Document, User


@pytest.mark.asyncio
async def test_upload_sets_user_id(async_client, db_session, patch_async_session):
    reg = await async_client.post("/auth/register", json={
        "email": "upload-owner@example.com",
        "password": "password123",
    })
    token = reg.json()["token"]
    user_id = reg.json()["user"]["id"]

    resp = await async_client.post(
        "/upload",
        files={"file": ("a.txt", b"hello world", "text/plain")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    doc = await db_session.get(Document, uuid.UUID(resp.json()["id"]))
    assert str(doc.user_id) == user_id


@pytest.mark.asyncio
async def test_identical_bytes_by_two_users_are_separate(async_client, db_session, patch_async_session):
    first = await async_client.post("/auth/register", json={
        "email": "first@example.com",
        "password": "password123",
    })
    second = await async_client.post("/auth/register", json={
        "email": "second@example.com",
        "password": "password123",
    })

    r1 = await async_client.post(
        "/upload",
        files={"file": ("a.txt", b"same bytes", "text/plain")},
        headers={"Authorization": f"Bearer {first.json()['token']}"},
    )
    r2 = await async_client.post(
        "/upload",
        files={"file": ("a.txt", b"same bytes", "text/plain")},
        headers={"Authorization": f"Bearer {second.json()['token']}"},
    )
    assert r1.json()["id"] != r2.json()["id"]


@pytest.mark.asyncio
async def test_identical_bytes_by_same_user_dedup(async_client, db_session, patch_async_session):
    reg = await async_client.post("/auth/register", json={
        "email": "dedup@example.com",
        "password": "password123",
    })
    headers = {"Authorization": f"Bearer {reg.json()['token']}"}

    r1 = await async_client.post(
        "/upload", files={"file": ("a.txt", b"dedup me", "text/plain")}, headers=headers,
    )
    r2 = await async_client.post(
        "/upload", files={"file": ("b.txt", b"dedup me", "text/plain")}, headers=headers,
    )
    assert r1.json()["id"] == r2.json()["id"]


SCHEMA = "from pydantic import BaseModel\n\nclass X(BaseModel):\n    y: str\n"


@pytest.mark.asyncio
async def test_extract_rejects_foreign_document(async_client, db_session, patch_async_session):
    owner = await async_client.post("/auth/register", json={
        "email": "owner@example.com",
        "password": "password123",
    })
    attacker = await async_client.post("/auth/register", json={
        "email": "attacker@example.com",
        "password": "password123",
    })
    doc = Document(
        user_id=uuid.UUID(owner.json()["user"]["id"]),
        filename="secret.txt", content_type="text/plain", file_size=1, storage_path="/dev/null",
    )
    db_session.add(doc)
    await db_session.commit()

    with patch("app.main.process_job"):
        resp = await async_client.post(
            "/extract",
            json={"document_id": str(doc.id), "pydantic_schema": SCHEMA},
            headers={"Authorization": f"Bearer {attacker.json()['token']}"},
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_extract_admin_can_access_foreign_document(async_client, db_session, patch_async_session):
    owner = await async_client.post("/auth/register", json={
        "email": "owner2@example.com",
        "password": "password123",
    })
    admin = await async_client.post("/auth/register", json={
        "email": "admin2@example.com",
        "password": "password123",
    })
    admin_user = (await db_session.execute(
        select(User).where(User.email == "admin2@example.com")
    )).scalar_one()
    admin_user.role = "admin"
    await db_session.commit()

    doc = Document(
        user_id=uuid.UUID(owner.json()["user"]["id"]),
        filename="secret.txt", content_type="text/plain", file_size=1, storage_path="/dev/null",
    )
    db_session.add(doc)
    await db_session.commit()

    with patch("app.main.process_job"):
        resp = await async_client.post(
            "/extract",
            json={"document_id": str(doc.id), "pydantic_schema": SCHEMA},
            headers={"Authorization": f"Bearer {admin.json()['token']}"},
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_extract_rejects_admin_only_model(async_client, db_session, patch_async_session):
    from app.models import ModelRegistry

    reg = await async_client.post("/auth/register", json={
        "email": "modeluser@example.com",
        "password": "password123",
    })
    db_session.add(ModelRegistry(connection_id=None, model_name="secret-model", enabled=True, admin_only=True))
    doc = Document(
        user_id=uuid.UUID(reg.json()["user"]["id"]),
        filename="t.txt", content_type="text/plain", file_size=1, storage_path="/dev/null",
    )
    db_session.add(doc)
    await db_session.commit()

    with patch("app.main.process_job"):
        resp = await async_client.post(
            "/extract",
            json={
                "document_id": str(doc.id),
                "pydantic_schema": SCHEMA,
                "model_id": "ollama/ollama/secret-model",
            },
            headers={"Authorization": f"Bearer {reg.json()['token']}"},
        )
    assert resp.status_code == 403
