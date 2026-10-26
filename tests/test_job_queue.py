import pytest
from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import select

import app.main as main_mod
from app.models import Document, ExtractionJob
from app.queue.base import QueueFull
from app.queue.inprocess import JobQueue


def test_slot_acquire_and_release():
    q = JobQueue(concurrency=2, max_waiting=1)
    assert q.try_reserve() is True
    assert q.try_reserve() is True
    assert q.try_reserve() is True   # concurrency 2 + 1 waiting
    assert q.try_reserve() is False  # queue full
    q.release()
    assert q.try_reserve() is True


def test_queue_respects_concurrency():
    q = JobQueue(concurrency=1, max_waiting=0)
    assert q.try_reserve() is True
    assert q.try_reserve() is False


@pytest.mark.asyncio
async def test_enqueue_rejects_when_queue_full(monkeypatch):
    import app.queue.inprocess as queue_mod

    full = JobQueue(concurrency=1, max_waiting=0)
    assert full.try_reserve() is True  # fill the only slot
    monkeypatch.setattr(queue_mod, "_queue", full)

    with pytest.raises(HTTPException) as exc:
        await main_mod._enqueue_jobs(BackgroundTasks(), [object()])
    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_rejected_enqueue_removes_the_created_jobs(
    db_session, patch_async_session, monkeypatch
):
    """Rows are committed before enqueue, so a 503 must delete them.

    Otherwise they stay `pending` forever and consume the backend cap.
    """

    class _FullBackend:
        async def enqueue(self, background_tasks, job_ids):
            raise QueueFull

    doc = Document(
        filename="t.txt", content_type="text/plain", file_size=1, storage_path="/dev/null"
    )
    db_session.add(doc)
    await db_session.commit()
    jobs = [
        ExtractionJob(document_id=doc.id, pydantic_schema="class X: pass")
        for _ in range(2)
    ]
    db_session.add_all(jobs)
    await db_session.commit()
    job_ids = [job.id for job in jobs]

    monkeypatch.setattr(main_mod, "get_backend", lambda: _FullBackend())

    with pytest.raises(HTTPException) as exc:
        await main_mod._enqueue_jobs(db_session, BackgroundTasks(), job_ids)
    assert exc.value.status_code == 503

    remaining = await db_session.execute(
        select(ExtractionJob).where(ExtractionJob.id.in_(job_ids))
    )
    assert remaining.scalars().all() == []
