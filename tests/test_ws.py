import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.testclient import TestClient

from app.main import app
from app.models import Document, ExtractionJob, JobStatus
from app.ws import ConnectionManager, manager


@pytest.mark.asyncio
async def test_connect_tracks_connection(patch_async_session):
    job_id = uuid.uuid4()
    client = TestClient(app)
    with client.websocket_connect(f"/ws/jobs/{job_id}"):
        assert job_id in manager.active
        assert len(manager.active[job_id]) == 1
    manager.active.pop(job_id, None)


@pytest.mark.asyncio
async def test_known_job_receives_status(db_session, patch_async_session):
    doc = Document(filename="t.txt", content_type="text/plain", file_size=1, storage_path="/dev/null")
    db_session.add(doc)
    await db_session.commit()
    job = ExtractionJob(document_id=doc.id, status=JobStatus.running, pydantic_schema="x")
    db_session.add(job)
    await db_session.commit()

    client = TestClient(app)
    with client.websocket_connect(f"/ws/jobs/{job.id}") as ws:
        data = ws.receive_json()
        assert data["event"] == "status"
        assert data["status"] == "running"
    manager.active.pop(job.id, None)


def test_manager_tracks_connections():
    cm = ConnectionManager()
    job_id = uuid.uuid4()
    ws1, ws2 = MagicMock(spec=["accept", "send_json"]), MagicMock(spec=["accept", "send_json"])
    ws1.accept = AsyncMock()
    ws2.accept = AsyncMock()

    async def connect():
        await cm.connect(job_id, ws1)
        await cm.connect(job_id, ws2)

    async def disconnect():
        cm.disconnect(job_id, ws1)

    anyio = pytest.importorskip("anyio")
    anyio.run(connect)
    assert len(cm.active[job_id]) == 2

    anyio.run(disconnect)
    assert len(cm.active[job_id]) == 1


def test_manager_notify():
    cm = ConnectionManager()
    job_id = uuid.uuid4()
    ws = MagicMock(spec=["accept", "send_json"])
    ws.accept = AsyncMock()
    ws.send_json = AsyncMock()

    async def run():
        await cm.connect(job_id, ws)
        await cm.notify(job_id, {"event": "status", "status": "running"})

    anyio = pytest.importorskip("anyio")
    anyio.run(run)
    ws.send_json.assert_awaited_once_with({"event": "status", "status": "running"})
