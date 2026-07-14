import uuid

from app.models import ExtractionJob, JobStatus


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
