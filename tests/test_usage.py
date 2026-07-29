import pytest

from app.pricing import calculate_cost


def test_cost_known_model():
    cost = calculate_cost("openai", "gpt-4o-mini", 1000, 500)
    # 1000 * 0.15 / 1M + 500 * 0.60 / 1M = 0.00015 + 0.00030 = 0.00045
    assert cost == pytest.approx(0.00045, rel=1e-3)


def test_cost_ollama_free():
    cost = calculate_cost("ollama", "qwen3.6:35b", 10000, 5000)
    assert cost == 0.0


def test_cost_prefix_match():
    cost = calculate_cost("openai", "gpt-4o-2024-08-06", 1000, 500)
    # Uses gpt-4o pricing: 1000 * 2.50 / 1M + 500 * 10.00 / 1M = 0.0025 + 0.005 = 0.0075
    assert cost == pytest.approx(0.0075, rel=1e-3)


def test_cost_unknown_model():
    cost = calculate_cost("openai", "some-random-model", 1000, 500)
    assert cost == 0.0


def test_cost_unknown_provider():
    cost = calculate_cost("nonexistent", "model", 1000, 500)
    assert cost == 0.0


@pytest.mark.asyncio
async def test_api_usage(async_client):
    reg = await async_client.post("/auth/register", json={
        "email": "usage-test@example.com",
        "password": "password123",
    })
    assert reg.status_code == 200
    token = reg.json()["token"]

    resp = await async_client.get("/api/usage", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "total_jobs" in data
    assert "total_input_tokens" in data
    assert "total_output_tokens" in data
    assert "total_cost" in data
