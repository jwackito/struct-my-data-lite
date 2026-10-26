"""In-process queue backend (spec 25).

Keeps today's bounded semaphore plus per-request reservation, so lite
behaviour is unchanged.
"""

import asyncio

from fastapi import BackgroundTasks

from app.config import settings
from app.processing import process_job
from app.queue.base import QueueFull


class JobQueue:
    """Bounded in-flight job limiter.

    `concurrency` jobs run at once; up to `max_waiting` more may be reserved
    before new submissions are rejected. Per-process and in-memory.
    """

    def __init__(self, concurrency: int, max_waiting: int):
        self.concurrency = max(1, concurrency)
        self.max_waiting = max(0, max_waiting)
        self._slots = asyncio.Semaphore(self.concurrency)
        self._reserved = 0
        self._cap = self.concurrency + self.max_waiting

    def try_reserve(self) -> bool:
        if self._reserved >= self._cap:
            return False
        self._reserved += 1
        return True

    def release(self) -> None:
        if self._reserved > 0:
            self._reserved -= 1

    async def run(self, coro):
        async with self._slots:
            try:
                return await coro
            finally:
                self.release()


_queue = JobQueue(settings.batch_concurrency, settings.job_queue_max)


class InProcessQueue:
    async def enqueue(self, background_tasks: BackgroundTasks, job_ids: list) -> None:
        reserved = 0
        for _ in job_ids:
            if not _queue.try_reserve():
                for _ in range(reserved):
                    _queue.release()
                raise QueueFull
            reserved += 1
        for job_id in job_ids:
            background_tasks.add_task(process_job, job_id)
