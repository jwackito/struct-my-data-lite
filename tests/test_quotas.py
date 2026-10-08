import pytest
from fastapi import HTTPException

from app.config import settings
from app.models import Document, ExtractionJob, JobStatus, User
from app.quotas import enforce_job_quota


@pytest.mark.asyncio
async def test_quota_disabled_by_default(db_session):
    user = User(email="u@example.com", password_hash="x", display_name="u", role="user")
    db_session.add(user)
    await db_session.commit()
    doc = Document(filename="t.txt", content_type="text/plain", file_size=1, storage_path="/dev/null")
    db_session.add(doc)
    await db_session.commit()
    for _ in range(5):
        db_session.add(ExtractionJob(
            user_id=user.id, document_id=doc.id, status=JobStatus.pending, pydantic_schema="x",
        ))
    await db_session.commit()

    await enforce_job_quota(db_session, user, 1)


@pytest.mark.asyncio
async def test_active_cap_rejects_over_limit(db_session, monkeypatch):
    monkeypatch.setattr(settings, "usage_enforced", True)
    monkeypatch.setattr(settings, "per_user_concurrency", 1)

    user = User(email="u@example.com", password_hash="x", display_name="u", role="user")
    db_session.add(user)
    await db_session.commit()
    doc = Document(filename="t.txt", content_type="text/plain", file_size=1, storage_path="/dev/null")
    db_session.add(doc)
    await db_session.commit()
    db_session.add(ExtractionJob(
        user_id=user.id, document_id=doc.id, status=JobStatus.running, pydantic_schema="x",
    ))
    await db_session.commit()

    with pytest.raises(HTTPException) as exc:
        await enforce_job_quota(db_session, user, 1)
    assert exc.value.status_code == 429
