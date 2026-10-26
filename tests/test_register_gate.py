"""Registration page gating (spec 26 D26-12)."""

import pytest


@pytest.mark.asyncio
async def test_register_page_is_open_when_registration_allowed(client):
    resp = await client.get("/register")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_register_page_is_closed_when_invite_only(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "invite_only", True)

    resp = await client.get("/register")

    assert resp.status_code == 403
    assert "Registration is closed" in resp.text
