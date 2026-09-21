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
