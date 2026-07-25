import asyncio
import time
import uuid
from datetime import datetime, timezone

from app.database import async_session
from app.extraction import ExtractionService
from app.models import Document, ExtractionJob, JobStatus
from app.parsers import get_parser as get_doc_parser
from app.providers import get_provider
from app.ws import manager


def _job_payload(job: ExtractionJob) -> dict:
    return {
        "event": "status",
        "job_id": str(job.id),
        "status": job.status.value if isinstance(job.status, JobStatus) else job.status,
        "output_data": job.output_data,
        "error_message": job.error_message,
        "input_tokens": job.input_tokens,
        "output_tokens": job.output_tokens,
        "upload_duration_ms": job.upload_duration_ms,
        "parsing_duration_ms": job.parsing_duration_ms,
        "llm_duration_ms": job.llm_duration_ms,
    }


async def process_job(job_id: uuid.UUID):
    async with async_session() as db:
        job = await db.get(ExtractionJob, job_id)
        if not job:
            return

        job.status = JobStatus.running
        await db.commit()
        await manager.notify(job_id, _job_payload(job))

        try:
            doc = await db.get(Document, job.document_id)
            if not doc:
                raise ValueError("Document not found")

            t0 = time.monotonic_ns()
            parser = get_doc_parser(doc.content_type)
            text = await asyncio.to_thread(parser.parse, doc.storage_path)
            job.parsing_duration_ms = (time.monotonic_ns() - t0) // 1_000_000

            provider = get_provider(job.provider_name or "ollama")
            model = job.model_name or getattr(provider, "model", "")
            client = provider.get_client(model_name=model)

            if doc.content_type.startswith("image/"):
                content = {"type": "image", "data": text, "format": doc.content_type.split("/")[1]}
            else:
                content = text

            def _on_response(result):
                raw = getattr(result, "_raw_response", None)
                if raw and raw.usage:
                    job.input_tokens = raw.usage.prompt_tokens
                    job.output_tokens = raw.usage.completion_tokens

            service = ExtractionService(client)
            t1 = time.monotonic_ns()
            result = await asyncio.to_thread(service.extract, content, job.pydantic_schema, model, on_response=_on_response)
            job.llm_duration_ms = (time.monotonic_ns() - t1) // 1_000_000

            job.output_data = result
            job.status = JobStatus.completed
        except Exception as e:
            job.error_message = str(e)
            job.status = JobStatus.failed
        finally:
            job.completed_at = datetime.now(timezone.utc)
            await db.commit()
            await manager.notify(job_id, _job_payload(job))
