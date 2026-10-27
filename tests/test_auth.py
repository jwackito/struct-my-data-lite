from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.auth import create_jwt, decode_jwt, hash_password, verify_password


def test_hash_and_verify_password():
    hashed = hash_password("my-secret-password")
    assert hashed != "my-secret-password"
    assert verify_password("my-secret-password", hashed) is True
    assert verify_password("wrong-password", hashed) is False


def test_create_and_decode_jwt():
    token = create_jwt("user-123", "admin")
    payload = decode_jwt(token)
    assert payload is not None
    assert payload["sub"] == "user-123"
    assert payload["role"] == "admin"


def test_decode_invalid_jwt():
    assert decode_jwt("not-a-valid-token") is None


def test_jwt_secret_required_outside_dev(monkeypatch):
    import app.auth as auth

    monkeypatch.setattr(auth.settings, "env", "prod")
    monkeypatch.setattr(auth.settings, "jwt_secret", "")
    monkeypatch.setattr(auth, "_jwt_secret_cache", None)

    with pytest.raises(RuntimeError):
        auth._jwt_secret()


def test_jwt_secret_falls_back_in_dev(monkeypatch):
    import app.auth as auth

    monkeypatch.setattr(auth.settings, "env", "dev")
    monkeypatch.setattr(auth.settings, "jwt_secret", "")
    monkeypatch.setattr(auth, "_jwt_secret_cache", None)

    assert auth._jwt_secret()


@pytest.mark.asyncio
async def test_get_current_user_no_token():
    from app.auth import get_current_user
    from fastapi import HTTPException
    from fastapi import Request

    mock_request = MagicMock(spec=Request)
    mock_request.headers = {}
    mock_request.cookies = {}

    with pytest.raises(HTTPException) as exc:
        await get_current_user(mock_request, AsyncMock())
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_invalid_token():
    from app.auth import get_current_user
    from fastapi import HTTPException
    from fastapi import Request

    mock_request = MagicMock(spec=Request)
    mock_request.headers = {"Authorization": "Bearer invalid-token"}
    mock_request.cookies = {}

    with pytest.raises(HTTPException) as exc:
        await get_current_user(mock_request, AsyncMock())
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_register_returns_token(async_client):
    resp = await async_client.post("/auth/register", json={
        "email": "test@example.com",
        "password": "password123",
        "display_name": "Test User",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data
    assert data["user"]["email"] == "test@example.com"
    assert data["user"]["display_name"] == "Test User"
    assert data["user"]["role"] == "user"


@pytest.mark.asyncio
async def test_register_runs_registration_validators(async_client, monkeypatch):
    from app import hooks

    seen = []

    async def validator(db, payload):
        seen.append(payload)

    monkeypatch.setattr(hooks, "_registration_validators", [validator])

    resp = await async_client.post("/auth/register", json={
        "email": "hooked@example.com",
        "password": "password123",
    })

    assert resp.status_code == 200
    assert seen[0]["email"] == "hooked@example.com"


@pytest.mark.asyncio
async def test_register_is_blocked_when_validator_raises(async_client, monkeypatch):
    from fastapi import HTTPException

    from app import hooks

    async def validator(db, payload):
        raise HTTPException(status_code=422, detail="invite required")

    monkeypatch.setattr(hooks, "_registration_validators", [validator])

    resp = await async_client.post("/auth/register", json={
        "email": "no-invite@example.com",
        "password": "password123",
    })

    assert resp.status_code == 422
    assert resp.json()["detail"] == "invite required"


@pytest.mark.asyncio
async def test_register_duplicate_email(async_client):
    await async_client.post("/auth/register", json={
        "email": "dup@example.com",
        "password": "password123",
    })
    resp = await async_client.post("/auth/register", json={
        "email": "dup@example.com",
        "password": "otherpass123",
    })
    assert resp.status_code == 422
    assert "already registered" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_login(async_client):
    await async_client.post("/auth/register", json={
        "email": "login-test@example.com",
        "password": "password123",
    })
    resp = await async_client.post("/auth/login", json={
        "email": "login-test@example.com",
        "password": "password123",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data


@pytest.mark.asyncio
async def test_login_wrong_password(async_client):
    await async_client.post("/auth/register", json={
        "email": "wrong@example.com",
        "password": "password123",
    })
    resp = await async_client.post("/auth/login", json={
        "email": "wrong@example.com",
        "password": "wrongpassword",
    })
    assert resp.status_code == 401
    assert "invalid" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_docs_requires_auth(async_client):
    resp = await async_client.get("/docs")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_docs_ok_with_auth(async_client):
    await async_client.post("/auth/register", json={
        "email": "docs@example.com",
        "password": "password123",
    })
    resp = await async_client.get("/docs")
    assert resp.status_code == 200
    assert "swagger" in resp.text.lower()


@pytest.mark.asyncio
async def test_openapi_requires_auth(async_client):
    resp = await async_client.get("/openapi.json")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_openapi_ok_with_auth(async_client):
    await async_client.post("/auth/register", json={
        "email": "openapi@example.com",
        "password": "password123",
    })
    resp = await async_client.get("/openapi.json")
    assert resp.status_code == 200
    assert resp.json()["openapi"]


@pytest.mark.asyncio
async def test_register_runs_post_registration_hooks(async_client, monkeypatch):
    from app import hooks

    seen = []

    async def hook(db, user):
        seen.append(user.email)

    monkeypatch.setattr(hooks, "_post_registration_hooks", [])
    hooks.register_post_registration_hook(hook)

    resp = await async_client.post(
        "/auth/register",
        json={"email": "post-hook@example.com", "password": "password123"},
    )

    assert resp.status_code == 200
    assert seen == ["post-hook@example.com"]
