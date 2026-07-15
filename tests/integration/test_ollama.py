import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.models import ExtractionJob, JobStatus
from app.processing import process_job
from tests.conftest import ollama_available

pytestmark = pytest.mark.skipif(not ollama_available(), reason="Ollama not available")


@pytest.mark.asyncio
async def test_real_extraction(async_client, db_session, patch_async_session):
    upload_resp = await async_client.post("/upload", files={"file": ("harry.txt", b"Harry is 11 years old")})
    doc_id = upload_resp.json()["id"]

    extract_resp = await async_client.post(
        "/extract",
        json={
            "document_id": doc_id,
            "pydantic_schema": (
                "from pydantic import BaseModel\n"
                "class Character(BaseModel):\n"
                "    name: str\n"
                "    age: int\n"
            ),
        },
    )
    job_id = extract_resp.json()["id"]

    await process_job(uuid.UUID(job_id))

    result = await db_session.execute(select(ExtractionJob).where(ExtractionJob.id == uuid.UUID(job_id)))
    job = result.scalar_one()
    assert job.status == JobStatus.completed
    assert job.output_data is not None
    assert "name" in job.output_data
    assert "age" in job.output_data


@pytest.mark.asyncio
async def test_ollama_unreachable(async_client, db_session, patch_async_session):
    upload_resp = await async_client.post("/upload", files={"file": ("doc.txt", b"data")})
    doc_id = upload_resp.json()["id"]

    extract_resp = await async_client.post(
        "/extract",
        json={
            "document_id": doc_id,
            "pydantic_schema": "from pydantic import BaseModel\nclass X(BaseModel):\n    y: str",
        },
    )
    job_id = extract_resp.json()["id"]

    with patch("app.providers.ollama.settings.ollama_host", "http://localhost:19999"):
        await process_job(uuid.UUID(job_id))

    result = await db_session.execute(select(ExtractionJob).where(ExtractionJob.id == uuid.UUID(job_id)))
    job = result.scalar_one()
    assert job.status == JobStatus.failed
    assert job.error_message is not None
