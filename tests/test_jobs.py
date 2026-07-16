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
