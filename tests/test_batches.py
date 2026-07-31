import pytest


@pytest.mark.asyncio
async def test_batch_creation_creates_job_per_document(async_client, db_session):
    reg = await async_client.post("/auth/register", json={
        "email": "batch-create@example.com",
        "password": "password123",
    })
    token = reg.json()["token"]

    from app.models import Document
    doc_ids = []
    for i in range(3):
        doc = Document(filename=f"doc{i}.txt", content_type="text/plain", file_size=10, storage_path=f"/tmp/doc{i}.txt")
        db_session.add(doc)
        await db_session.flush()
        doc_ids.append(str(doc.id))
    await db_session.commit()

    resp = await async_client.post("/api/batches", json={
        "document_ids": doc_ids,
        "pydantic_schema": "class X(BaseModel): pass",
        "model_id": "ollama/ollama/qwen3.6:35b",
    }, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "batch_id" in data
    assert len(data["job_ids"]) == 3


@pytest.mark.asyncio
async def test_batch_progress(async_client, db_session):
    reg = await async_client.post("/auth/register", json={
        "email": "batch-progress@example.com",
        "password": "password123",
    })
    token = reg.json()["token"]

    from app.models import Batch, Document
    from sqlalchemy import select
    batch = Batch(name="test-batch", user_id=reg.json()["user"]["id"])
    db_session.add(batch)
    await db_session.flush()

    from app.models import ExtractionJob
    for i in range(2):
        doc = Document(filename=f"p{i}.txt", content_type="text/plain", file_size=10, storage_path=f"/tmp/p{i}.txt")
        db_session.add(doc)
        await db_session.flush()
        job = ExtractionJob(batch_id=batch.id, document_id=doc.id, user_id=reg.json()["user"]["id"],
                            pydantic_schema="class X: pass", status="completed",
                            input_tokens=10, output_tokens=5, model_name="qwen3.6:35b")
        db_session.add(job)
    await db_session.commit()

    resp = await async_client.get(f"/api/batches/{batch.id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert data["completed"] == 2
    assert len(data["jobs"]) == 2


@pytest.mark.asyncio
async def test_batch_retry_failed(async_client, db_session):
    reg = await async_client.post("/auth/register", json={
        "email": "batch-retry@example.com",
        "password": "password123",
    })
    token = reg.json()["token"]

    from app.models import Batch, Document, ExtractionJob
    batch = Batch(name="retry-batch", user_id=reg.json()["user"]["id"])
    db_session.add(batch)
    await db_session.flush()

    doc = Document(filename="f.txt", content_type="text/plain", file_size=10, storage_path="/tmp/f.txt")
    db_session.add(doc)
    await db_session.flush()

    job = ExtractionJob(batch_id=batch.id, document_id=doc.id, user_id=reg.json()["user"]["id"],
                        pydantic_schema="class X: pass", status="failed",
                        error_message="boom", model_name="qwen3.6:35b")
    db_session.add(job)
    await db_session.commit()

    resp = await async_client.post(f"/api/batches/{batch.id}/retry-failed", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["retried"] == [str(job.id)]

    progress = await async_client.get(f"/api/batches/{batch.id}", headers={"Authorization": f"Bearer {token}"})
    assert progress.json()["jobs"][0]["status"] == "pending"


