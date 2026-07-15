import uuid

import pytest
from sqlalchemy import select

from app.models import Document, ExtractionJob


@pytest.mark.asyncio
async def test_upload_creates_document(async_client, db_session):
    response = await async_client.post(
        "/upload",
        files={"file": ("test.txt", b"hello world")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "test.txt"
    assert data["file_size"] == 11
    assert data["content_type"] == "text/plain"

    result = await db_session.execute(select(Document).where(Document.id == uuid.UUID(data["id"])))
    doc = result.scalar_one()
    assert doc.filename == "test.txt"


@pytest.mark.asyncio
async def test_upload_content_hash(async_client, db_session):
    content = b"unique-content-42"
    resp1 = await async_client.post("/upload", files={"file": ("a.txt", content)})
    resp2 = await async_client.post("/upload", files={"file": ("b.txt", content)})
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert resp1.json()["id"] == resp2.json()["id"]


@pytest.mark.asyncio
async def test_extract_creates_job(async_client, db_session):
    upload_resp = await async_client.post("/upload", files={"file": ("doc.txt", b"some text")})
    doc_id = upload_resp.json()["id"]

    response = await async_client.post(
        "/extract",
        json={
            "document_id": doc_id,
            "pydantic_schema": "from pydantic import BaseModel\nclass X(BaseModel):\n    y: str",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pending"

    result = await db_session.execute(select(ExtractionJob).where(ExtractionJob.id == uuid.UUID(data["id"])))
    job = result.scalar_one()
    assert str(job.document_id) == doc_id


@pytest.mark.asyncio
async def test_get_job_status(async_client, db_session):
    upload_resp = await async_client.post("/upload", files={"file": ("doc.txt", b"some text")})
    doc_id = upload_resp.json()["id"]

    extract_resp = await async_client.post(
        "/extract",
        json={
            "document_id": doc_id,
            "pydantic_schema": "from pydantic import BaseModel\nclass X(BaseModel):\n    y: str",
        },
    )
    job_id = extract_resp.json()["id"]

    response = await async_client.get(f"/jobs/{job_id}")
    assert response.status_code == 200
    assert response.json()["document_id"] == doc_id
    assert "status" in response.json()
    assert "created_at" in response.json()


@pytest.mark.asyncio
async def test_get_job_not_found(async_client):
    response = await async_client.get(f"/jobs/{uuid.uuid4()}")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_extract_missing_document(async_client):
    response = await async_client.post(
        "/extract",
        json={
            "document_id": str(uuid.uuid4()),
            "pydantic_schema": "from pydantic import BaseModel\nclass X(BaseModel):\n    y: str",
        },
    )
    assert response.status_code == 404
