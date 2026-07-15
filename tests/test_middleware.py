import pytest


@pytest.mark.asyncio
async def test_response_has_request_id(client):
    response = await client.get("/health")
    assert "X-Request-ID" in response.headers
    assert len(response.headers["X-Request-ID"]) == 36  # UUID length


@pytest.mark.asyncio
async def test_error_response_has_request_id(client):
    response = await client.get("/notfound")
    assert response.status_code == 404
    assert "X-Request-ID" in response.headers
