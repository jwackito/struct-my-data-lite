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
async def test_batch_retry_failed(async_client, db_session, monkeypatch):
    import asyncio
    from unittest.mock import AsyncMock
    monkeypatch.setattr("app.main.process_job", AsyncMock())

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


@pytest.mark.asyncio
async def test_batch_cancel_pending(async_client, db_session):
    reg = await async_client.post("/auth/register", json={
        "email": "batch-cancel@example.com",
        "password": "password123",
    })
    token = reg.json()["token"]

    from app.models import Batch, Document, ExtractionJob
    batch = Batch(name="cancel-batch", user_id=reg.json()["user"]["id"])
    db_session.add(batch)
    await db_session.flush()

    doc = Document(filename="c.txt", content_type="text/plain", file_size=10, storage_path="/tmp/c.txt")
    db_session.add(doc)
    await db_session.flush()

    job = ExtractionJob(batch_id=batch.id, document_id=doc.id, user_id=reg.json()["user"]["id"],
                        pydantic_schema="class X: pass", status="pending", model_name="qwen3.6:35b")
    db_session.add(job)
    await db_session.commit()

    resp = await async_client.post(f"/api/batches/{batch.id}/cancel", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["cancelled"] == [str(job.id)]

    progress = await async_client.get(f"/api/batches/{batch.id}", headers={"Authorization": f"Bearer {token}"})
    assert progress.json()["jobs"][0]["status"] == "failed"
    assert "Cancelled" in progress.json()["jobs"][0]["error_message"]


@pytest.mark.asyncio
async def test_batch_results_download(async_client, db_session):
    reg = await async_client.post("/auth/register", json={
        "email": "batch-results@example.com",
        "password": "password123",
    })
    token = reg.json()["token"]

    from app.models import Batch, Document, ExtractionJob
    batch = Batch(name="results-batch", user_id=reg.json()["user"]["id"])
    db_session.add(batch)
    await db_session.flush()

    doc = Document(filename="r.txt", content_type="text/plain", file_size=10, storage_path="/tmp/r.txt")
    db_session.add(doc)
    await db_session.flush()

    job = ExtractionJob(batch_id=batch.id, document_id=doc.id, user_id=reg.json()["user"]["id"],
                        pydantic_schema="class X: pass", status="completed",
                        input_tokens=10, output_tokens=5, model_name="qwen3.6:35b",
                        output_data={"name": "test"})
    db_session.add(job)
    await db_session.commit()

    resp = await async_client.get(f"/api/batches/{batch.id}/results", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["batch_id"] == str(batch.id)
    assert len(data["results"]) == 1
    assert data["results"][0]["filename"] == "r.txt"
    assert data["results"][0]["output_data"] == {"name": "test"}


@pytest.mark.asyncio
async def test_batch_size_limit_rejects_51_files(async_client):
    reg = await async_client.post("/auth/register", json={
        "email": "batch-limit@example.com",
        "password": "password123",
    })
    token = reg.json()["token"]

    fake_ids = [str(i) for i in range(51)]
    resp = await async_client.post("/api/batches", json={
        "document_ids": fake_ids,
        "pydantic_schema": "class X: pass",
    }, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 422
    assert "max size" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_batch_estimate(async_client):
    reg = await async_client.post("/auth/register", json={
        "email": "batch-estimate@example.com",
        "password": "password123",
    })
    token = reg.json()["token"]

    resp = await async_client.post("/api/batches/estimate", json={
        "file_sizes": [4000, 4000],
        "model_id": "openai/openai/gpt-4o-mini",
    }, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["documents"] == 2
    assert data["estimated_tokens"] > 0
    assert data["estimated_cost"] > 0
    assert data["model"] == "gpt-4o-mini"


@pytest.mark.asyncio
async def test_batch_multipart_sets_hx_redirect(async_client, db_session, monkeypatch):
    import asyncio
    from unittest.mock import AsyncMock
    monkeypatch.setattr("app.main.process_job", AsyncMock())

    reg = await async_client.post("/auth/register", json={
        "email": "batch-multipart@example.com",
        "password": "password123",
    })
    token = reg.json()["token"]

    files = [
        ("file", ("a.txt", b"content a", "text/plain")),
        ("file", ("b.txt", b"content b", "text/plain")),
        ("file", ("c.txt", b"content c", "text/plain")),
    ]
    resp = await async_client.post(
        "/ui/batch-extract",
        data={"pydantic_schema": "class X(BaseModel): pass", "model_id": "ollama/ollama/qwen3.6:35b"},
        files=files,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert "HX-Redirect" in resp.headers
    assert resp.headers["HX-Redirect"].startswith("/ui/batches/")

    from app.models import Batch
    from sqlalchemy import select
    result = await db_session.execute(select(Batch))
    batches = result.scalars().all()
    assert len(batches) == 1
    from app.models import ExtractionJob
    jobs = await db_session.execute(select(ExtractionJob).where(ExtractionJob.batch_id == batches[0].id))
    assert len(jobs.scalars().all()) == 3


@pytest.mark.asyncio
async def test_single_file_upload_creates_batch_of_one(async_client, db_session, monkeypatch):
    import asyncio
    from unittest.mock import AsyncMock
    monkeypatch.setattr("app.main.process_job", AsyncMock())

    reg = await async_client.post("/auth/register", json={
        "email": "batch-single@example.com",
        "password": "password123",
    })
    token = reg.json()["token"]

    resp = await async_client.post(
        "/ui/batch-extract",
        data={"pydantic_schema": "class X(BaseModel): pass", "model_id": "ollama/ollama/qwen3.6:35b"},
        files=[("file", ("single.txt", b"content", "text/plain"))],
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert "HX-Redirect" in resp.headers

    from app.models import Batch, ExtractionJob
    from sqlalchemy import select
    result = await db_session.execute(select(Batch))
    batches = result.scalars().all()
    assert len(batches) == 1
    jobs = await db_session.execute(select(ExtractionJob).where(ExtractionJob.batch_id == batches[0].id))
    job_list = jobs.scalars().all()
    assert len(job_list) == 1
    assert job_list[0].batch_id == batches[0].id






