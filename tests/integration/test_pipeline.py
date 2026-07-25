import time as time_module
import uuid
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select

from app.models import ExtractionJob, JobStatus
from app.processing import process_job


@pytest.mark.asyncio
async def test_pipeline_invalid_schema(async_client, db_session, patch_async_session):
    upload_resp = await async_client.post("/upload", files={"file": ("input.txt", b"some data")})
    doc_id = upload_resp.json()["id"]

    extract_resp = await async_client.post(
        "/extract",
        json={
            "document_id": doc_id,
            "pydantic_schema": "this is not valid python",
        },
    )
    assert extract_resp.status_code == 422
    assert "invalid" in extract_resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_full_pipeline_with_mock_llm(async_client, db_session, patch_async_session):
    upload_resp = await async_client.post("/upload", files={"file": ("input.txt", b"Alice is 30 years old")})
    doc_id = upload_resp.json()["id"]

    extract_resp = await async_client.post(
        "/extract",
        json={
            "document_id": doc_id,
            "pydantic_schema": (
                "from pydantic import BaseModel\n"
                "class Person(BaseModel):\n"
                "    name: str\n"
                "    age: int\n"
            ),
        },
    )
    job_id = extract_resp.json()["id"]

    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"name": "Alice", "age": 30}
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_result

    with patch("app.processing.get_provider") as mock_get_provider:
        mock_provider = MagicMock()
        mock_provider.get_client.return_value = mock_client
        mock_provider.model = "test-model"
        mock_get_provider.return_value = mock_provider
        await process_job(uuid.UUID(job_id))

    result = await db_session.execute(select(ExtractionJob).where(ExtractionJob.id == uuid.UUID(job_id)))
    job = result.scalar_one()
    assert job.status == JobStatus.completed
    assert job.output_data == {"name": "Alice", "age": 30}


@pytest.mark.asyncio
async def test_process_job_records_tokens(async_client, db_session, patch_async_session):
    upload_resp = await async_client.post("/upload", files={"file": ("input.txt", b"Alice is 30")})
    doc_id = upload_resp.json()["id"]

    extract_resp = await async_client.post(
        "/extract",
        json={
            "document_id": doc_id,
            "pydantic_schema": (
                "from pydantic import BaseModel\n"
                "class Person(BaseModel):\n"
                "    name: str\n"
                "    age: int\n"
            ),
        },
    )
    job_id = extract_resp.json()["id"]

    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 42
    mock_usage.completion_tokens = 7

    mock_raw = MagicMock()
    mock_raw.usage = mock_usage

    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"name": "Alice", "age": 30}
    mock_result._raw_response = mock_raw

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_result

    with patch("app.processing.get_provider") as mock_get_provider:
        mock_provider = MagicMock()
        mock_provider.get_client.return_value = mock_client
        mock_provider.model = "test-model"
        mock_get_provider.return_value = mock_provider
        await process_job(uuid.UUID(job_id))

    result = await db_session.execute(select(ExtractionJob).where(ExtractionJob.id == uuid.UUID(job_id)))
    job = result.scalar_one()
    assert job.input_tokens == 42
    assert job.output_tokens == 7
    assert job.status == JobStatus.completed


@pytest.mark.asyncio
async def test_process_job_records_timing(async_client, db_session, patch_async_session):
    upload_resp = await async_client.post("/upload", files={"file": ("input.txt", b"Bob is 25")})
    doc_id = upload_resp.json()["id"]

    extract_resp = await async_client.post(
        "/extract",
        json={
            "document_id": doc_id,
            "pydantic_schema": (
                "from pydantic import BaseModel\n"
                "class Person(BaseModel):\n"
                "    name: str\n"
                "    age: int\n"
            ),
        },
    )
    job_id = extract_resp.json()["id"]

    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 10
    mock_usage.completion_tokens = 5

    mock_raw = MagicMock()
    mock_raw.usage = mock_usage

    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"name": "Bob", "age": 25}
    mock_result._raw_response = mock_raw

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_result

    with patch("app.processing.get_provider") as mock_get_provider:
        mock_provider = MagicMock()
        mock_provider.get_client.return_value = mock_client
        mock_provider.model = "test-model"
        mock_get_provider.return_value = mock_provider
        await process_job(uuid.UUID(job_id))

    result = await db_session.execute(select(ExtractionJob).where(ExtractionJob.id == uuid.UUID(job_id)))
    job = result.scalar_one()
    assert job.parsing_duration_ms is not None
    assert job.parsing_duration_ms >= 0
    assert job.llm_duration_ms is not None
    assert job.llm_duration_ms >= 0
    assert job.status == JobStatus.completed
