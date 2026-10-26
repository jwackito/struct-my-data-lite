"""Tests for the queue backend abstraction (spec 25).

Lite uses the in-process backend; the arq backend is cloud-only and absent
here, so `get_backend` must fail with a clear edition error.
"""

import pytest
from fastapi import BackgroundTasks

from app import queue as queue_mod
from app.queue.base import QueueFull
from app.queue.inprocess import InProcessQueue, JobQueue


def test_get_backend_defaults_to_inprocess():
    assert isinstance(queue_mod.get_backend(), InProcessQueue)


def test_get_backend_rejects_unknown_backend(monkeypatch):
    monkeypatch.setattr(queue_mod.settings, "queue_backend", "rabbitmq")
    with pytest.raises(RuntimeError, match="Unknown queue backend"):
        queue_mod.get_backend()


def test_get_backend_arq_without_cloud_module(monkeypatch):
    monkeypatch.setattr(queue_mod.settings, "queue_backend", "arq")
    with pytest.raises(RuntimeError, match="cloud edition"):
        queue_mod.get_backend()


@pytest.mark.asyncio
async def test_inprocess_enqueue_adds_one_task_per_job(monkeypatch):
    from app.queue import inprocess

    monkeypatch.setattr(inprocess, "_queue", JobQueue(concurrency=2, max_waiting=2))
    tasks = BackgroundTasks()

    await InProcessQueue().enqueue(tasks, ["job-1", "job-2"])

    assert [task.args[0] for task in tasks.tasks] == ["job-1", "job-2"]


@pytest.mark.asyncio
async def test_inprocess_enqueue_releases_reservations_when_full(monkeypatch):
    from app.queue import inprocess

    full = JobQueue(concurrency=1, max_waiting=1)
    monkeypatch.setattr(inprocess, "_queue", full)

    with pytest.raises(QueueFull):
        await InProcessQueue().enqueue(BackgroundTasks(), ["a", "b", "c"])

    # The two successful reservations must be released, leaving the queue usable.
    assert full.try_reserve() is True
    assert full.try_reserve() is True
    assert full.try_reserve() is False
