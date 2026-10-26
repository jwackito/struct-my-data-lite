import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_lifespan_requires_jwt_secret_outside_dev(monkeypatch):
    import app.auth as auth
    from app.main import app, lifespan

    monkeypatch.setattr(auth.settings, "env", "prod")
    monkeypatch.setattr(auth.settings, "jwt_secret", "")
    monkeypatch.setattr(auth, "_jwt_secret_cache", None)
    monkeypatch.setattr("app.main.settings.skip_db_wait", True)

    with pytest.raises(RuntimeError):
        async with lifespan(app):
            pass


@pytest.mark.asyncio
async def test_lifespan_runs_registered_hooks(monkeypatch):
    from app import hooks
    from app.main import app, lifespan

    seen = []

    async def hook(application):
        seen.append(application)

    monkeypatch.setattr(hooks, "_lifespan_hooks", [hook])
    monkeypatch.setattr("app.main.settings.skip_db_wait", True)

    async with lifespan(app):
        pass

    assert seen == [app]


@pytest.mark.asyncio
async def test_wait_for_db_succeeds():
    from app.database import wait_for_db

    engine = MagicMock()
    conn = AsyncMock()
    engine.connect.return_value.__aenter__.return_value = conn

    await wait_for_db(engine, retries=1, delay=0)
    engine.connect.assert_called_once()


@pytest.mark.asyncio
async def test_wait_for_db_raises_after_retries():
    from app.database import wait_for_db

    engine = MagicMock()
    engine.connect.side_effect = Exception("DB unreachable")

    with pytest.raises(Exception, match="DB unreachable"):
        await wait_for_db(engine, retries=3, delay=0)

    assert engine.connect.call_count == 3
