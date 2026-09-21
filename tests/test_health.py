import pytest


@pytest.mark.asyncio
async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_ready_ok(async_client):
    response = await async_client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_ready_db_unavailable(async_client, monkeypatch):
    import app.main as main_mod

    class BoomSession:
        async def __aenter__(self):
            raise RuntimeError("db down")

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(main_mod, "async_session", lambda: BoomSession())
    response = await async_client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
