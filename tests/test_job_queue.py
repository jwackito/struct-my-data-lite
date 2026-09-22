import asyncio

import pytest

from app import processing


@pytest.mark.asyncio
async def test_slot_acquire_and_release(monkeypatch):
    q = processing.JobQueue(concurrency=2, max_waiting=1, monotonic=lambda: 0.0)
    assert q.try_reserve() is True
    assert q.try_reserve() is True
    assert q.try_reserve() is True   # concurrency 2 + 1 waiting
    assert q.try_reserve() is False  # queue full
    q.release()
    assert q.try_reserve() is True


@pytest.mark.asyncio
async def test_queue_respects_concurrency(monkeypatch):
    q = processing.JobQueue(concurrency=1, max_waiting=0)
    assert q.try_reserve() is True
    assert q.try_reserve() is False
