import pytest
from fastapi import BackgroundTasks, HTTPException

import app.main as main_mod
from app import processing
from app.processing import JobQueue


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


def test_enqueue_rejects_when_queue_full(monkeypatch):
    full = JobQueue(concurrency=1, max_waiting=0)
    assert full.try_reserve() is True  # fill the only slot
    monkeypatch.setattr(main_mod, "try_reserve_slot", full.try_reserve)

    with pytest.raises(HTTPException) as exc:
        main_mod._enqueue_jobs(BackgroundTasks(), [object()])
    assert exc.value.status_code == 503
