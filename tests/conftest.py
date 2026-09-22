import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.database import get_db
from app.main import app
from app.models import Base

settings.skip_db_wait = True

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@test-db:5432/structmydata_test",
)


@pytest.fixture(autouse=True)
def _disable_rate_limits(monkeypatch):
    import app.processing as proc_mod
    import app.main as main_mod
    from app.ratelimit import TokenBucket

    monkeypatch.setattr(
        main_mod,
        "_rate_limiters",
        {
            "auth": TokenBucket(10**9, 60),
            "extract": TokenBucket(10**9, 60),
            "batch": TokenBucket(10**9, 60),
        },
    )
    monkeypatch.setattr(proc_mod, "_queue", proc_mod.JobQueue(10**6, 10**6))


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as cli:
        yield cli


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine):
    async with test_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())
    async with AsyncSession(test_engine, expire_on_commit=False) as session:
        yield session


def _patch_async_session(engine):
    import app.database as db_mod
    import app.processing as proc_mod
    import app.main as main_mod
    test_sm = async_sessionmaker(engine, expire_on_commit=False)
    originals = {
        "database": db_mod.async_session,
        "processing": proc_mod.async_session,
        "main": main_mod.async_session,
    }
    db_mod.async_session = test_sm
    proc_mod.async_session = test_sm
    main_mod.async_session = test_sm
    return originals


def _restore_async_session(originals):
    import app.database as db_mod
    import app.processing as proc_mod
    import app.main as main_mod
    db_mod.async_session = originals["database"]
    proc_mod.async_session = originals["processing"]
    main_mod.async_session = originals["main"]


@pytest_asyncio.fixture
async def async_client(test_engine, db_session):
    saved = _patch_async_session(test_engine)

    app.dependency_overrides.clear()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    _restore_async_session(saved)


@pytest_asyncio.fixture
async def patch_async_session(test_engine):
    saved = _patch_async_session(test_engine)
    yield
    _restore_async_session(saved)


def ollama_available():
    import urllib.request
    try:
        urllib.request.urlopen("http://host.docker.internal:11434/api/tags", timeout=2)
        return True
    except Exception:
        return False
