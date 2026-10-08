import uuid

import pytest

from app.models import Document


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
