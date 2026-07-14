import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.database import async_session
from app.extraction import ExtractionService
from app.models import Document, ExtractionJob, JobStatus
from app.parsers import get_parser as get_doc_parser
from app.providers import get_provider


async def process_job(job_id: uuid.UUID):
    async with async_session() as db:
        job = await db.get(ExtractionJob, job_id)
        if not job:
            return

        job.status = JobStatus.running
        await db.commit()

        try:
            doc = await db.get(Document, job.document_id)
            if not doc:
                raise ValueError("Document not found")

            parser = get_doc_parser(doc.content_type)
            text = parser.parse(doc.storage_path)

            provider = get_provider("ollama")
            client = provider.get_client()

            service = ExtractionService(client)
            result = service.extract(text, job.pydantic_schema)

            job.output_data = result
            job.status = JobStatus.completed
        except Exception as e:
            job.error_message = str(e)
            job.status = JobStatus.failed
        finally:
            job.completed_at = datetime.now(timezone.utc)
            await db.commit()
