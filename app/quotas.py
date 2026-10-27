from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.hooks import resolve_plan_limits
from app.i18n import t_req
from app.models import ExtractionJob, JobStatus, User


async def enforce_job_quota(db: AsyncSession, user: User, new_jobs: int = 1) -> None:
    """DB-backed per-user caps.

    A registered plan-limits provider (cloud, spec 27) supplies the caps and
    enforces them regardless of `usage_enforced`; without one, lite keeps the
    settings-gated behaviour (D18-13).

    Locks the user row so concurrent creations cannot race past the active-job
    cap (D18-7). Raises HTTP 429 when a cap would be exceeded.
    """
    limits = await resolve_plan_limits(db, user)
    if limits is None and not settings.usage_enforced:
        return

    concurrency = (limits or {}).get("per_user_concurrency", settings.per_user_concurrency)
    daily_cap = (limits or {}).get("daily_job_cap", settings.daily_job_cap)

    await db.execute(select(User.id).where(User.id == user.id).with_for_update())

    active = await db.execute(
        select(func.count())
        .select_from(ExtractionJob)
        .where(
            ExtractionJob.user_id == user.id,
            ExtractionJob.status.in_([JobStatus.pending, JobStatus.running]),
        )
    )
    if active.scalar_one() + new_jobs > concurrency:
        raise HTTPException(status_code=429, detail=t_req("Too many active jobs, try again shortly"))

    if daily_cap > 0:
        start = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
        daily = await db.execute(
            select(func.count())
            .select_from(ExtractionJob)
            .where(
                ExtractionJob.user_id == user.id,
                ExtractionJob.created_at >= start,
            )
        )
        if daily.scalar_one() + new_jobs > daily_cap:
            raise HTTPException(status_code=429, detail=t_req("Daily job limit reached"))


async def plan_max_batch_size(db: AsyncSession, user: User) -> int:
    """The smaller of the deployment limit and the plan's `max_batch_size`."""
    limits = await resolve_plan_limits(db, user)
    cap = (limits or {}).get("max_batch_size")
    return min(settings.max_batch_size, cap) if cap else settings.max_batch_size


async def enforce_vision_batch(db: AsyncSession, user: User, image_count: int) -> None:
    """Reject batches with more `image/*` documents than the plan allows (D27-17)."""
    if image_count <= 0:
        return
    limits = await resolve_plan_limits(db, user)
    cap = (limits or {}).get("vision_batch_max")
    if cap is not None and image_count > cap:
        raise HTTPException(
            status_code=422,
            detail=t_req("Vision batches are limited to {max} document(s)", max=cap),
        )
