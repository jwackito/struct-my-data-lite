import uuid
from unittest.mock import MagicMock, AsyncMock

import pytest
from starlette.testclient import TestClient

from app.main import app
from app.ws import ConnectionManager, manager


def test_connect_disconnect():
    job_id = uuid.uuid4()
    client = TestClient(app)
    with client.websocket_connect(f"/ws/jobs/{job_id}"):
        assert job_id in manager.active
        assert len(manager.active[job_id]) == 1
    assert job_id not in manager.active


def test_unknown_job_receives_status():
    client = TestClient(app)
    with client.websocket_connect("/ws/jobs/00000000-0000-0000-0000-000000000000") as ws:
        data = ws.receive_json()
        assert data["event"] == "status"
        assert data["status"] == "pending"


def test_manager_tracks_connections():
    cm = ConnectionManager()
    job_id = uuid.uuid4()
    ws1, ws2 = MagicMock(spec=["send_json"]), MagicMock(spec=["send_json"])

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
    ws = MagicMock(spec=["send_json"])
    ws.send_json = AsyncMock()

    async def run():
        await cm.connect(job_id, ws)
        await cm.notify(job_id, {"event": "status", "status": "running"})

    anyio = pytest.importorskip("anyio")
    anyio.run(run)
    ws.send_json.assert_awaited_once_with({"event": "status", "status": "running"})
