import asyncio
from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

engine = create_async_engine(settings.database_url)
async_session = async_sessionmaker(engine, expire_on_commit=False)


async def wait_for_db(eng=None, retries: int = 30, delay: int = 1):
    eng = eng or engine
    for i in range(retries):
        try:
            async with eng.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return
        except Exception:
            if i == retries - 1:
                raise
            await asyncio.sleep(delay)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session
