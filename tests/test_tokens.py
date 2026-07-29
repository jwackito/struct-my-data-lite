import hashlib

import pytest

from app.auth import generate_api_token


def test_generate_api_token():
    raw, token_hash, prefix = generate_api_token()
    assert raw.startswith("smd_")
    assert len(raw) > 40
    assert prefix == raw[:8]
    assert token_hash == hashlib.sha256(raw.encode()).hexdigest()


@pytest.mark.asyncio
async def test_create_and_list_tokens(async_client):
    reg = await async_client.post("/auth/register", json={
        "email": "token-test@example.com",
        "password": "password123",
    })
    assert reg.status_code == 200
    token = reg.json()["token"]

    # Create a token
    resp = await async_client.post(
        "/api/tokens",
        json={"name": "ci-pipeline"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "ci-pipeline"
    assert data["token"].startswith("smd_")
    assert data["prefix"] == data["token"][:8]
    full_token = data["token"]

    # List tokens (raw token not included)
    resp = await async_client.get(
        "/api/tokens",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    tokens = resp.json()["tokens"]
    assert len(tokens) == 1
    assert tokens[0]["prefix"] == full_token[:8]
    assert "token" not in tokens[0]

    # Auth with the new token
    resp = await async_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {full_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["email"] == "token-test@example.com"

    # Revoke
    resp = await async_client.delete(
        f"/api/tokens/{tokens[0]['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    # Auth with revoked token fails
    resp = await async_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {full_token}"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_token_requires_name(async_client):
    reg = await async_client.post("/auth/register", json={
        "email": "token-name-test@example.com",
        "password": "password123",
    })
    token = reg.json()["token"]

    resp = await async_client.post(
        "/api/tokens",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422
