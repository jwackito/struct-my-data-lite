from unittest.mock import patch

import uuid

import pytest

from app.models import Document, ExtractionJob, JobStatus


class TestExtractionJobModel:
    def test_default_status_is_pending(self):
        job = ExtractionJob(
            document_id=uuid.uuid4(),
            pydantic_schema="from pydantic import BaseModel\nclass X(BaseModel):\n    y: str",
        )
        assert job.status == JobStatus.pending

    def test_status_enum_values(self):
        assert JobStatus.pending.value == "pending"
        assert JobStatus.running.value == "running"
        assert JobStatus.completed.value == "completed"
        assert JobStatus.failed.value == "failed"

    def test_job_id_is_uuid(self):
        job = ExtractionJob(
            document_id=uuid.uuid4(),
            pydantic_schema="class X: pass",
        )
        assert isinstance(job.id, uuid.UUID)

    def test_job_has_input_tokens_field(self):
        job = ExtractionJob(
            document_id=uuid.uuid4(),
            pydantic_schema="class X: pass",
        )
        assert hasattr(job, "input_tokens")
        assert job.input_tokens is None

    def test_job_has_output_tokens_field(self):
        job = ExtractionJob(
            document_id=uuid.uuid4(),
            pydantic_schema="class X: pass",
        )
        assert hasattr(job, "output_tokens")
        assert job.output_tokens is None

    def test_job_has_upload_duration_field(self):
        job = ExtractionJob(
            document_id=uuid.uuid4(),
            pydantic_schema="class X: pass",
        )
        assert hasattr(job, "upload_duration_ms")
        assert job.upload_duration_ms is None

    def test_job_has_parsing_duration_field(self):
        job = ExtractionJob(
            document_id=uuid.uuid4(),
            pydantic_schema="class X: pass",
        )
        assert hasattr(job, "parsing_duration_ms")
        assert job.parsing_duration_ms is None

    def test_job_has_llm_duration_field(self):
        job = ExtractionJob(
            document_id=uuid.uuid4(),
            pydantic_schema="class X: pass",
        )
        assert hasattr(job, "llm_duration_ms")
        assert job.llm_duration_ms is None

    def test_job_has_provider_name_field(self):
        job = ExtractionJob(
            document_id=uuid.uuid4(),
            pydantic_schema="class X: pass",
        )
        assert hasattr(job, "provider_name")
        assert job.provider_name is None

    def test_job_has_model_name_field(self):
        job = ExtractionJob(
            document_id=uuid.uuid4(),
            pydantic_schema="class X: pass",
        )
        assert hasattr(job, "model_name")
        assert job.model_name is None


@pytest.mark.asyncio
async def test_ui_jobs_list_empty(async_client, db_session, patch_async_session):
    resp = await async_client.get("/ui/jobs")
    assert resp.status_code == 200
    assert "<table>" in resp.text
    assert "<tbody></tbody>" in resp.text or "<tbody>" in resp.text


@pytest.mark.asyncio
async def test_ui_jobs_list_returns_rows(async_client, db_session, patch_async_session):
    doc = Document(filename="t.txt", content_type="text/plain", file_size=1, storage_path="/dev/null")
    db_session.add(doc)
    await db_session.commit()

    for i in range(2):
        j = ExtractionJob(document_id=doc.id, pydantic_schema="from pydantic import BaseModel\nclass X(BaseModel):\n  y: str")
        db_session.add(j)
    await db_session.commit()

    resp = await async_client.get("/ui/jobs")
    assert resp.status_code == 200
    assert resp.text.count("<tr>") == 3  # header + 2 data rows
    assert "✅" in resp.text or "⏳" in resp.text
    assert "View" in resp.text


@pytest.mark.asyncio
async def test_ui_jobs_pagination(async_client, db_session, patch_async_session):
    doc = Document(filename="t.txt", content_type="text/plain", file_size=1, storage_path="/dev/null")
    db_session.add(doc)
    await db_session.commit()

    for i in range(25):
        j = ExtractionJob(document_id=doc.id, pydantic_schema="from pydantic import BaseModel\nclass X(BaseModel):\n  y: str")
        db_session.add(j)
    await db_session.commit()

    page1 = await async_client.get("/ui/jobs?offset=0&limit=20")
    assert page1.status_code == 200
    assert page1.text.count("<tr>") == 21

    page2 = await async_client.get("/ui/jobs?offset=20&limit=20")
    assert page2.status_code == 200
    assert page2.text.count("<tr>") == 6


@pytest.mark.asyncio
async def test_ui_jobs_shows_retry_for_failed(async_client, db_session, patch_async_session):
    doc = Document(filename="t.txt", content_type="text/plain", file_size=1, storage_path="/dev/null")
    db_session.add(doc)
    await db_session.commit()

    failed_job = ExtractionJob(document_id=doc.id, status=JobStatus.failed, pydantic_schema="x", error_message="oops")
    db_session.add(failed_job)

    ok_job = ExtractionJob(document_id=doc.id, status=JobStatus.completed, pydantic_schema="y", output_data={})
    db_session.add(ok_job)
    await db_session.commit()

    resp = await async_client.get("/ui/jobs")
    assert resp.status_code == 200
    assert resp.text.count("Retry") == 1


@pytest.mark.asyncio
async def test_retry_failed_job(async_client, db_session, patch_async_session):
    doc = Document(filename="t.txt", content_type="text/plain", file_size=1, storage_path="/dev/null")
    db_session.add(doc)
    await db_session.commit()

    job = ExtractionJob(document_id=doc.id, status=JobStatus.failed, pydantic_schema="x", error_message="oops")
    db_session.add(job)
    await db_session.commit()

    with patch("app.main.process_job"):
        resp = await async_client.post(f"/ui/jobs/{job.id}/retry")
    assert resp.status_code == 200

    await db_session.refresh(job)
    assert job.status == JobStatus.pending
    assert job.error_message is None
    assert job.completed_at is None


@pytest.mark.asyncio
async def test_retry_completed_job_rejected(async_client, db_session, patch_async_session):
    doc = Document(filename="t.txt", content_type="text/plain", file_size=1, storage_path="/dev/null")
    db_session.add(doc)
    await db_session.commit()

    job = ExtractionJob(document_id=doc.id, status=JobStatus.completed, pydantic_schema="x", output_data={})
    db_session.add(job)
    await db_session.commit()

    resp = await async_client.post(f"/ui/jobs/{job.id}/retry")
    assert resp.status_code == 200
    assert "Can only retry" in resp.text

    await db_session.refresh(job)
    assert job.status == JobStatus.completed


@pytest.mark.asyncio
async def test_retry_missing_job(async_client, db_session, patch_async_session):
    resp = await async_client.post(f"/ui/jobs/{uuid.uuid4()}/retry")
    assert resp.status_code == 200
    assert "not found" in resp.text.lower()


@pytest.mark.asyncio
async def test_retry_triggers_processing(async_client, db_session, patch_async_session):
    doc = Document(filename="t.txt", content_type="text/plain", file_size=1, storage_path="/dev/null")
    db_session.add(doc)
    await db_session.commit()

    job = ExtractionJob(document_id=doc.id, status=JobStatus.failed, pydantic_schema="x", error_message="oops")
    db_session.add(job)
    await db_session.commit()

    resp = await async_client.post(f"/ui/jobs/{job.id}/retry")
    assert resp.status_code == 200
    assert "Retrying" in resp.text


@pytest.mark.asyncio
async def test_retry_resets_tokens_and_timing(async_client, db_session, patch_async_session):
    doc = Document(filename="t.txt", content_type="text/plain", file_size=1, storage_path="/dev/null")
    db_session.add(doc)
    await db_session.commit()

    job = ExtractionJob(
        document_id=doc.id,
        status=JobStatus.failed,
        pydantic_schema="x",
        error_message="oops",
        input_tokens=100,
        output_tokens=20,
        parsing_duration_ms=50,
        llm_duration_ms=200,
        upload_duration_ms=10,
    )
    db_session.add(job)
    await db_session.commit()

    with patch("app.main.process_job"):
        resp = await async_client.post(f"/ui/jobs/{job.id}/retry")
    assert resp.status_code == 200

    await db_session.refresh(job)
    assert job.input_tokens is None
    assert job.output_tokens is None
    assert job.parsing_duration_ms is None
    assert job.llm_duration_ms is None
    assert job.upload_duration_ms == 10


@pytest.mark.asyncio
async def test_ui_job_detail_shows_tokens(async_client, db_session, patch_async_session):
    doc = Document(filename="t.txt", content_type="text/plain", file_size=1, storage_path="/dev/null")
    db_session.add(doc)
    await db_session.commit()

    job = ExtractionJob(
        document_id=doc.id,
        status=JobStatus.completed,
        pydantic_schema="x",
        output_data={"name": "test"},
        input_tokens=100,
        output_tokens=20,
        parsing_duration_ms=50,
        llm_duration_ms=200,
        upload_duration_ms=10,
    )
    db_session.add(job)
    await db_session.commit()

    resp = await async_client.get(f"/ui/jobs/{job.id}")
    assert resp.status_code == 200
    assert "100" in resp.text
    assert "20" in resp.text
