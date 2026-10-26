import time as time_module
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from app.models import ExtractionJob, JobStatus
from app.processing import process_job

REGISTER = {
    "email": "pipeline@example.com",
    "password": "password123",
}


@pytest.mark.asyncio
async def test_failed_job_records_error_detail(async_client, db_session, patch_async_session):
    await async_client.post("/auth/register", json=REGISTER)
    upload_resp = await async_client.post(
        "/upload",
        files={"file": ("archive.zip", b"not a supported document", "application/zip")},
    )
    doc_id = upload_resp.json()["id"]

    extract_resp = await async_client.post(
        "/extract",
        json={
            "document_id": doc_id,
            "pydantic_schema": (
                "from pydantic import BaseModel\n"
                "class Person(BaseModel):\n"
                "    name: str\n"
            ),
        },
    )
    job_id = extract_resp.json()["id"]

    await process_job(uuid.UUID(job_id))

    result = await db_session.execute(select(ExtractionJob).where(ExtractionJob.id == uuid.UUID(job_id)))
    job = result.scalar_one()
    assert job.status == JobStatus.failed
    assert "Unsupported content type" in job.error_message
    assert job.error_detail is not None
    assert "ValueError" in job.error_detail
    assert "Unsupported content type" in job.error_detail


@pytest.mark.asyncio
async def test_pipeline_invalid_schema(async_client, db_session, patch_async_session):
    await async_client.post("/auth/register", json=REGISTER)
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
    await async_client.post("/auth/register", json=REGISTER)
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
    await async_client.post("/auth/register", json=REGISTER)
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
    await async_client.post("/auth/register", json=REGISTER)
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


@pytest.mark.asyncio
async def test_process_job_notify_failure_sets_failed(async_client, db_session, patch_async_session):
    """First manager.notify failure must not leave job stuck in non-terminal state."""
    await async_client.post("/auth/register", json=REGISTER)
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

    mock_notify = AsyncMock(side_effect=[Exception("notify failure"), None])

    with patch("app.events.manager.notify", mock_notify):
        with patch("app.processing.get_provider") as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.get_client.return_value = MagicMock()
            mock_get_provider.return_value = mock_provider
            await process_job(uuid.UUID(job_id))

    result = await db_session.execute(select(ExtractionJob).where(ExtractionJob.id == uuid.UUID(job_id)))
    job = result.scalar_one()
    assert job.status == JobStatus.failed
    assert "notify failure" in job.error_message


@pytest.mark.asyncio
async def test_pipeline_parses_octet_stream_docx_by_extension(async_client, db_session, patch_async_session):
    import io

    from docx import Document

    buf = io.BytesIO()
    doc = Document()
    doc.add_paragraph("Alice is 30 years old")
    doc.save(buf)
    docx_bytes = buf.getvalue()

    await async_client.post("/auth/register", json=REGISTER)
    upload_resp = await async_client.post(
        "/upload",
        files={"file": ("report.docx", docx_bytes, "application/octet-stream")},
    )
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
async def test_job_completion_hooks_run_before_commit(
    async_client, db_session, patch_async_session, monkeypatch
):
    from app import hooks

    seen = []

    async def hook(db, job, user):
        seen.append((job.status, job.completed_at, user.email))

    monkeypatch.setattr(hooks, "_job_completion_hooks", [hook])

    await async_client.post("/auth/register", json=REGISTER)
    upload_resp = await async_client.post(
        "/upload", files={"file": ("input.txt", b"Alice is 30 years old")}
    )
    with patch("app.queue.inprocess.process_job"):
        extract_resp = await async_client.post(
            "/extract",
            json={
                "document_id": upload_resp.json()["id"],
                "pydantic_schema": (
                    "from pydantic import BaseModel\n"
                    "class Person(BaseModel):\n"
                    "    name: str\n"
                ),
            },
        )

    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"name": "Alice"}
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_result

    with patch("app.processing.get_provider") as mock_get_provider:
        mock_provider = MagicMock()
        mock_provider.get_client.return_value = mock_client
        mock_get_provider.return_value = mock_provider
        await process_job(uuid.UUID(extract_resp.json()["id"]))

    status, completed_at, email = seen[0]
    assert status == JobStatus.completed
    assert completed_at is not None
    assert email == REGISTER["email"]
