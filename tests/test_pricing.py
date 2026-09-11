import pytest

from app.models import LLMConnection, ModelRegistry
from app.pricing import CUSTOM_PRICING, calculate_cost, refresh_pricing


def test_calculate_cost_static():
    assert calculate_cost("openai", "gpt-4o", 1_000_000, 0) == pytest.approx(2.50)


def test_calculate_cost_prefix_fallback():
    assert calculate_cost("openai", "gpt-4o-2024-08", 1_000_000, 0) == pytest.approx(2.50)


def test_calculate_cost_default_zero():
    assert calculate_cost("ollama", "any-model", 1_000_000, 1_000_000) == 0.0


@pytest.mark.asyncio
async def test_refresh_pricing_collapses_registry(async_client, db_session):
    conn = LLMConnection(name="c1", provider="openai")
    db_session.add(conn)
    await db_session.flush()

    first = ModelRegistry(connection_id=conn.id, model_name="gpt-4o", enabled=True,
                          price_input_usd=1.0, price_output_usd=2.0)
    db_session.add(first)
    second_conn = LLMConnection(name="c2", provider="openai")
    db_session.add(second_conn)
    await db_session.flush()
    dup = ModelRegistry(connection_id=second_conn.id, model_name="gpt-4o", enabled=True,
                        price_input_usd=9.0, price_output_usd=9.0)
    db_session.add(dup)
    await db_session.commit()

    try:
        await refresh_pricing(db_session)
        assert CUSTOM_PRICING["openai"]["gpt-4o"] == (1.0, 2.0)
        assert calculate_cost("openai", "gpt-4o", 1_000_000, 0) == pytest.approx(1.0)
        assert calculate_cost("openai", "gpt-4o", 0, 1_000_000) == pytest.approx(2.0)
    finally:
        CUSTOM_PRICING.clear()


@pytest.mark.asyncio
async def test_refresh_pricing_skips_disabled(async_client, db_session):
    conn = LLMConnection(name="c1", provider="gemini")
    db_session.add(conn)
    await db_session.flush()
    db_session.add(ModelRegistry(connection_id=conn.id, model_name="gemini-2.0-flash",
                                 enabled=False, price_input_usd=0.5, price_output_usd=1.5))
    await db_session.commit()

    try:
        await refresh_pricing(db_session)
        assert "gemini-2.0-flash" not in CUSTOM_PRICING.get("gemini", {})
        assert calculate_cost("gemini", "gemini-2.0-flash", 1_000_000, 0) == pytest.approx(0.10)
    finally:
        CUSTOM_PRICING.clear()