import pytest
from unittest.mock import AsyncMock


@pytest.mark.asyncio
async def test_wait_for_db_succeeds():
    from app.database import wait_for_db

    engine = AsyncMock()
    conn = AsyncMock()
    engine.connect.return_value.__aenter__.return_value = conn

    await wait_for_db(engine, retries=1, delay=0)
    engine.connect.assert_awaited_once()


@pytest.mark.asyncio
async def test_wait_for_db_raises_after_retries():
    from app.database import wait_for_db

    engine = AsyncMock()
    engine.connect.side_effect = Exception("DB unreachable")

    with pytest.raises(Exception, match="DB unreachable"):
        await wait_for_db(engine, retries=3, delay=0)

    assert engine.connect.await_count == 3
