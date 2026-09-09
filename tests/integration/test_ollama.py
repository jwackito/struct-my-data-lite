import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.models import ExtractionJob, JobStatus
from app.processing import process_job
from tests.conftest import ollama_available

pytestmark = pytest.mark.skipif(not ollama_available(), reason="Ollama not available")

REGISTER = {
    "email": "ollama@example.com",
    "password": "password123",
}


@pytest.mark.asyncio
async def test_real_extraction(async_client, db_session, patch_async_session):
    await async_client.post("/auth/register", json=REGISTER)
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
async def test_image_extraction_with_ollama(async_client, db_session, patch_async_session):
    await async_client.post("/auth/register", json=REGISTER)
    import io
    import struct
    import zlib

    def _tiny_png() -> bytes:
        sig = b"\x89PNG\r\n\x1a\n"
        ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
        ihdr_crc = zlib.crc32(b"IHDR" + ihdr_data) & 0xFFFFFFFF
        ihdr = struct.pack(">I", 13) + b"IHDR" + ihdr_data + struct.pack(">I", ihdr_crc)
        raw = zlib.compress(b"\x00\xff\x00\x00")
        idat_crc = zlib.crc32(b"IDAT" + raw) & 0xFFFFFFFF
        idat = struct.pack(">I", len(raw)) + b"IDAT" + raw + struct.pack(">I", idat_crc)
        iend_crc = zlib.crc32(b"IEND") & 0xFFFFFFFF
        iend = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", iend_crc)
        return sig + ihdr + idat + iend

    png_bytes = _tiny_png()

    upload_resp = await async_client.post(
        "/upload", files={"file": ("pixel.png", png_bytes, "image/png")}
    )
    doc_id = upload_resp.json()["id"]

    extract_resp = await async_client.post(
        "/extract",
        json={
            "document_id": doc_id,
            "pydantic_schema": (
                "from pydantic import BaseModel\n"
                "class ImageInfo(BaseModel):\n"
                "    width: int\n"
                "    height: int\n"
            ),
        },
    )
    job_id = extract_resp.json()["id"]

    await process_job(uuid.UUID(job_id))

    result = await db_session.execute(select(ExtractionJob).where(ExtractionJob.id == uuid.UUID(job_id)))
    job = result.scalar_one()
    assert job.status == JobStatus.completed
    assert job.output_data is not None


@pytest.mark.asyncio
async def test_ollama_unreachable(async_client, db_session, patch_async_session):
    await async_client.post("/auth/register", json=REGISTER)
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
