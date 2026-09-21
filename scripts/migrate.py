import asyncio
import sys

from sqlalchemy import text

from app.database import async_session

LOCK_KEY = 727234001


async def run() -> int:
    async with async_session() as session:
        await session.execute(text("SELECT pg_advisory_lock(:key)"), {"key": LOCK_KEY})
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "alembic", "upgrade", "head"
            )
            return await proc.wait()
        finally:
            await session.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_KEY})


def main() -> None:
    raise SystemExit(asyncio.run(run()))


if __name__ == "__main__":
    main()
