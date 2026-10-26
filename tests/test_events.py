"""Tests for job event fan-out (spec 25)."""

import uuid

import pytest

from app import events


class _FakeManager:
    def __init__(self):
        self.calls = []

    async def notify(self, job_id, payload):
        self.calls.append((job_id, payload))


@pytest.fixture
def fake_manager(monkeypatch):
    manager = _FakeManager()
    monkeypatch.setattr(events, "manager", manager)
    monkeypatch.setattr(events, "_publisher", None)
    return manager


@pytest.mark.asyncio
async def test_publish_notifies_local_clients(fake_manager):
    payload = {"event": "status", "job_id": str(uuid.uuid4())}

    await events.publish_job_update(payload)

    assert fake_manager.calls == [(uuid.UUID(payload["job_id"]), payload)]


@pytest.mark.asyncio
async def test_publish_calls_registered_publisher_before_local_notify(
    fake_manager, monkeypatch
):
    order = []

    async def publisher(payload):
        order.append("publisher")

    async def notify(job_id, payload):
        order.append("notify")

    monkeypatch.setattr(events, "_publisher", publisher)
    monkeypatch.setattr(fake_manager, "notify", notify)

    await events.publish_job_update({"event": "status", "job_id": str(uuid.uuid4())})

    assert order == ["publisher", "notify"]


def test_set_publisher_registers_callback(monkeypatch):
    monkeypatch.setattr(events, "_publisher", None)

    async def publisher(payload):
        return None

    events.set_publisher(publisher)

    assert events._publisher is publisher
