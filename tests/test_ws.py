import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.auth import create_jwt
from app.main import app
from app.models import Document, ExtractionJob, JobStatus, User
from app.ws import ConnectionManager, manager


def test_ws_rejects_without_token(patch_async_session):
    client = TestClient(app)
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(f"/ws/jobs/{uuid.uuid4()}"):
            pass
    assert exc.value.code == 4401


@pytest.mark.asyncio
async def test_connect_tracks_connection(db_session, patch_async_session):
    user = User(email="ws@example.com", password_hash="x", display_name="w", role="user")
    db_session.add(user)
    await db_session.commit()
    doc = Document(filename="t.txt", content_type="text/plain", file_size=1, storage_path="/dev/null")
    db_session.add(doc)
    await db_session.flush()
    job = ExtractionJob(user_id=user.id, document_id=doc.id, status=JobStatus.running, pydantic_schema="x")
    db_session.add(job)
    await db_session.commit()
    token = create_jwt(str(user.id), user.role)

    client = TestClient(app)
    with client.websocket_connect(f"/ws/jobs/{job.id}", cookies={"token": token}):
        assert job.id in manager.active
        assert len(manager.active[job.id]) == 1
    manager.active.pop(job.id, None)


@pytest.mark.asyncio
async def test_known_job_receives_status(db_session, patch_async_session):
    user = User(email="ws2@example.com", password_hash="x", display_name="w", role="user")
    db_session.add(user)
    await db_session.commit()
    doc = Document(filename="t.txt", content_type="text/plain", file_size=1, storage_path="/dev/null")
    db_session.add(doc)
    await db_session.flush()
    job = ExtractionJob(user_id=user.id, document_id=doc.id, status=JobStatus.running, pydantic_schema="x")
    db_session.add(job)
    await db_session.commit()
    token = create_jwt(str(user.id), user.role)

    client = TestClient(app)
    with client.websocket_connect(f"/ws/jobs/{job.id}", cookies={"token": token}) as ws:
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
