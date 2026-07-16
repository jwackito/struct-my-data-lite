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
