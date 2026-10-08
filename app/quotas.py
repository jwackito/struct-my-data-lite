from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.i18n import t_req
from app.models import ExtractionJob, JobStatus, User


async def enforce_job_quota(db: AsyncSession, user: User, new_jobs: int = 1) -> None:
    """DB-backed per-user caps, gated by the usage_enforced master switch (D18-13).

    Locks the user row so concurrent creations cannot race past the active-job
    cap (D18-7). Raises HTTP 429 when a cap would be exceeded.
    """
    if not settings.usage_enforced:
        return

    await db.execute(select(User.id).where(User.id == user.id).with_for_update())

    active = await db.execute(
        select(func.count())
        .select_from(ExtractionJob)
        .where(
            ExtractionJob.user_id == user.id,
            ExtractionJob.status.in_([JobStatus.pending, JobStatus.running]),
        )
    )
    if active.scalar_one() + new_jobs > settings.per_user_concurrency:
        raise HTTPException(status_code=429, detail=t_req("Too many active jobs, try again shortly"))

    if settings.daily_job_cap > 0:
        start = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
        daily = await db.execute(
            select(func.count())
            .select_from(ExtractionJob)
            .where(
                ExtractionJob.user_id == user.id,
                ExtractionJob.created_at >= start,
            )
        )
        if daily.scalar_one() + new_jobs > settings.daily_job_cap:
            raise HTTPException(status_code=429, detail=t_req("Daily job limit reached"))
