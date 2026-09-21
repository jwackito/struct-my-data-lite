import asyncio
import os

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

MIGRATION_DB_URL = os.getenv(
    "MIGRATION_DB_URL",
    "postgresql+asyncpg://postgres:postgres@test-db:5432/structmydata_test_migrations",
)
_ADMIN_DB_URL = os.getenv(
    "MIGRATION_ADMIN_DB_URL",
    "postgresql+asyncpg://postgres:postgres@test-db:5432/postgres",
)


@pytest_asyncio.fixture
async def migration_engine():
    engine = create_async_engine(MIGRATION_DB_URL)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        admin_engine = create_async_engine(
            _ADMIN_DB_URL,
            isolation_level="AUTOCOMMIT",
        )
        async with admin_engine.connect() as conn:
            await conn.execute(text("CREATE DATABASE structmydata_test_migrations"))
        await admin_engine.dispose()

    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))
        await conn.execute(text("""
            DO $$ DECLARE r RECORD; BEGIN
                FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
                    EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(r.tablename) || ' CASCADE';
                END LOOP;
            END $$;
        """))
    yield engine
    await engine.dispose()


@pytest.mark.asyncio
async def test_alembic_upgrade_head(migration_engine):
    proc = await asyncio.create_subprocess_shell(
        f"DATABASE_URL={MIGRATION_DB_URL} python -m alembic upgrade head",
        cwd="/app",
    )
    await proc.wait()
    assert proc.returncode == 0, f"upgrade failed (exit {proc.returncode})"

    async with migration_engine.begin() as conn:
        result = await conn.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        )
        tables = [r[0] for r in result.fetchall()]
        assert "documents" in tables
        assert "extraction_jobs" in tables


@pytest.mark.asyncio
async def test_alembic_downgrade_and_reupgrade(migration_engine):
    proc_up = await asyncio.create_subprocess_shell(
        f"DATABASE_URL={MIGRATION_DB_URL} python -m alembic upgrade head",
        cwd="/app",
    )
    await proc_up.wait()
    assert proc_up.returncode == 0

    proc_down = await asyncio.create_subprocess_shell(
        f"DATABASE_URL={MIGRATION_DB_URL} python -m alembic downgrade -1",
        cwd="/app",
    )
    await proc_down.wait()
    assert proc_down.returncode == 0, f"downgrade failed (exit {proc_down.returncode})"

    proc_up2 = await asyncio.create_subprocess_shell(
        f"DATABASE_URL={MIGRATION_DB_URL} python -m alembic upgrade head",
        cwd="/app",
    )
    await proc_up2.wait()
    assert proc_up2.returncode == 0
