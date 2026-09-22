import pytest


@pytest.mark.asyncio
async def test_auth_login_rate_limited(async_client, monkeypatch):
    import app.main as main_mod
    from app.ratelimit import TokenBucket

    monkeypatch.setitem(main_mod._rate_limiters, "auth", TokenBucket(rate=3, per_seconds=60))

    codes = []
    for _ in range(5):
        r = await async_client.post("/auth/login", json={"email": "x@example.com", "password": "nope12345"})
        codes.append(r.status_code)

    assert 429 in codes
    limited = [c for c in codes if c == 429]
    assert len(limited) >= 2


@pytest.mark.asyncio
async def test_rate_limit_response_has_retry_after(async_client, monkeypatch):
    import app.main as main_mod
    from app.ratelimit import TokenBucket

    monkeypatch.setitem(main_mod._rate_limiters, "auth", TokenBucket(rate=1, per_seconds=60))
    await async_client.post("/auth/login", json={"email": "y@example.com", "password": "nope12345"})
    r = await async_client.post("/auth/login", json={"email": "y@example.com", "password": "nope12345"})
    assert r.status_code == 429
    assert "Retry-After" in r.headers
