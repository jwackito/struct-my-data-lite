"""Creation-time plan checks wired into the shared routes (spec 27)."""

from unittest.mock import AsyncMock

import pytest

from app import hooks


async def _user_and_doc(async_client):
    await async_client.post(
        "/auth/register",
        json={"email": "plan-hooks@example.com", "password": "password123"},
    )
    upload = await async_client.post(
        "/upload", files={"file": ("input.txt", b"Alice is 30")}
    )
    return upload.json()["id"]


def _spy(monkeypatch, seen):
    async def validator(db, user, provider_type, new_jobs, estimate_usd):
        seen.append((provider_type, new_jobs, estimate_usd))

    monkeypatch.setattr(hooks, "_job_creation_validators", [validator])


@pytest.mark.asyncio
async def test_extract_runs_creation_validators(
    async_client, db_session, patch_async_session, monkeypatch
):
    doc_id = await _user_and_doc(async_client)
    seen = []
    _spy(monkeypatch, seen)
    monkeypatch.setattr("app.queue.inprocess.process_job", AsyncMock())

    resp = await async_client.post(
        "/extract",
        json={
            "document_id": doc_id,
            "pydantic_schema": "from pydantic import BaseModel\nclass X(BaseModel):\n    y: str",
        },
    )

    assert resp.status_code == 200
    assert seen == [("ollama", 1, None)]


@pytest.mark.asyncio
async def test_extract_propagates_rejection(
    async_client, db_session, patch_async_session, monkeypatch
):
    from fastapi import HTTPException

    doc_id = await _user_and_doc(async_client)

    async def validator(db, user, provider_type, new_jobs, estimate_usd):
        raise HTTPException(status_code=402, detail="Insufficient credit")

    monkeypatch.setattr(hooks, "_job_creation_validators", [validator])
    monkeypatch.setattr("app.queue.inprocess.process_job", AsyncMock())

    resp = await async_client.post(
        "/extract",
        json={
            "document_id": doc_id,
            "pydantic_schema": "from pydantic import BaseModel\nclass X(BaseModel):\n    y: str",
        },
    )

    assert resp.status_code == 402


@pytest.mark.asyncio
async def test_batch_create_passes_an_estimate(
    async_client, db_session, patch_async_session, monkeypatch
):
    doc_id = await _user_and_doc(async_client)
    seen = []
    _spy(monkeypatch, seen)
    monkeypatch.setattr("app.queue.inprocess.process_job", AsyncMock())

    resp = await async_client.post(
        "/api/batches",
        json={
            "document_ids": [doc_id],
            "pydantic_schema": "from pydantic import BaseModel\nclass X(BaseModel):\n    y: str",
        },
    )

    assert resp.status_code == 200
    provider_type, new_jobs, estimate = seen[0]
    assert provider_type == "ollama"
    assert new_jobs == 1
    assert estimate == 0.0


@pytest.mark.asyncio
async def test_retry_failed_runs_creation_validators(
    async_client, db_session, patch_async_session, monkeypatch
):
    import uuid
    from datetime import datetime, timezone

    from app.models import ExtractionJob, JobStatus

    doc_id = await _user_and_doc(async_client)
    seen = []
    _spy(monkeypatch, seen)
    monkeypatch.setattr("app.queue.inprocess.process_job", AsyncMock())

    created = await async_client.post(
        "/api/batches",
        json={
            "document_ids": [doc_id],
            "pydantic_schema": "from pydantic import BaseModel\nclass X(BaseModel):\n    y: str",
        },
    )
    batch_id = created.json()["batch_id"]
    job_id = created.json()["job_ids"][0]

    job = await db_session.get(ExtractionJob, uuid.UUID(job_id))
    job.status = JobStatus.failed
    job.completed_at = datetime.now(timezone.utc)
    await db_session.commit()
    seen.clear()

    resp = await async_client.post(f"/api/batches/{batch_id}/retry-failed")

    assert resp.status_code == 200
    assert seen and seen[0][1] == 1


@pytest.mark.asyncio
async def test_single_job_retry_runs_creation_validators(
    async_client, db_session, patch_async_session, monkeypatch
):
    import uuid
    from datetime import datetime, timezone

    from app.models import ExtractionJob, JobStatus

    doc_id = await _user_and_doc(async_client)
    seen = []
    _spy(monkeypatch, seen)
    monkeypatch.setattr("app.queue.inprocess.process_job", AsyncMock())

    created = await async_client.post(
        "/extract",
        json={
            "document_id": doc_id,
            "pydantic_schema": "from pydantic import BaseModel\nclass X(BaseModel):\n    y: str",
        },
    )
    job_id = created.json()["id"]
    job = await db_session.get(ExtractionJob, uuid.UUID(job_id))
    job.status = JobStatus.failed
    job.completed_at = datetime.now(timezone.utc)
    await db_session.commit()
    seen.clear()

    resp = await async_client.post(f"/ui/jobs/{job_id}/retry")

    assert resp.status_code == 200
    assert seen and seen[0][1] == 1
