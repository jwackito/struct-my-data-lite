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


@pytest.mark.asyncio
async def test_active_cap_is_per_user(db_session, monkeypatch):
    monkeypatch.setattr(settings, "usage_enforced", True)
    monkeypatch.setattr(settings, "per_user_concurrency", 1)

    alice = User(email="alice@example.com", password_hash="x", display_name="a", role="user")
    bob = User(email="bob@example.com", password_hash="x", display_name="b", role="user")
    db_session.add_all([alice, bob])
    await db_session.commit()
    doc = Document(filename="t.txt", content_type="text/plain", file_size=1, storage_path="/dev/null")
    db_session.add(doc)
    await db_session.commit()
    db_session.add(ExtractionJob(
        user_id=alice.id, document_id=doc.id, status=JobStatus.running, pydantic_schema="x",
    ))
    await db_session.commit()

    await enforce_job_quota(db_session, bob, 1)


@pytest.mark.asyncio
async def test_daily_cap_rejects_over_limit(db_session, monkeypatch):
    monkeypatch.setattr(settings, "usage_enforced", True)
    monkeypatch.setattr(settings, "per_user_concurrency", 100)
    monkeypatch.setattr(settings, "daily_job_cap", 1)

    user = User(email="u@example.com", password_hash="x", display_name="u", role="user")
    db_session.add(user)
    await db_session.commit()
    doc = Document(filename="t.txt", content_type="text/plain", file_size=1, storage_path="/dev/null")
    db_session.add(doc)
    await db_session.commit()
    db_session.add(ExtractionJob(
        user_id=user.id, document_id=doc.id, status=JobStatus.completed, pydantic_schema="x",
    ))
    await db_session.commit()

    with pytest.raises(HTTPException) as exc:
        await enforce_job_quota(db_session, user, 1)
    assert exc.value.status_code == 429


async def _user_with_active_job(db_session, status=JobStatus.running):
    user = User(email="plan@example.com", password_hash="x", display_name="u", role="user")
    db_session.add(user)
    await db_session.commit()
    doc = Document(filename="t.txt", content_type="text/plain", file_size=1, storage_path="/dev/null")
    db_session.add(doc)
    await db_session.commit()
    db_session.add(ExtractionJob(
        user_id=user.id, document_id=doc.id, status=status, pydantic_schema="x",
    ))
    await db_session.commit()
    return user


@pytest.mark.asyncio
async def test_plan_limits_apply_without_the_usage_flag(db_session, monkeypatch):
    from app import hooks

    limits = {"per_user_concurrency": 1, "daily_job_cap": 0}

    async def provider(db, user):
        return limits

    monkeypatch.setattr(hooks, "_plan_limits_provider", provider)
    monkeypatch.setattr(settings, "usage_enforced", False)
    user = await _user_with_active_job(db_session)

    with pytest.raises(HTTPException) as exc:
        await enforce_job_quota(db_session, user, 1)
    assert exc.value.status_code == 429


@pytest.mark.asyncio
async def test_no_plan_limits_keeps_settings_behaviour(db_session, monkeypatch):
    from app import hooks

    monkeypatch.setattr(hooks, "_plan_limits_provider", None)
    monkeypatch.setattr(settings, "usage_enforced", False)
    user = await _user_with_active_job(db_session)

    await enforce_job_quota(db_session, user, 1)


@pytest.mark.asyncio
async def test_plan_max_batch_size_caps_settings(db_session, monkeypatch):
    from app import hooks
    from app.quotas import plan_max_batch_size

    async def provider(db, user):
        return {"max_batch_size": 3}

    monkeypatch.setattr(hooks, "_plan_limits_provider", provider)
    monkeypatch.setattr(settings, "max_batch_size", 50)

    assert await plan_max_batch_size(db_session, object()) == 3


@pytest.mark.asyncio
async def test_plan_max_batch_size_without_provider(db_session, monkeypatch):
    from app import hooks
    from app.quotas import plan_max_batch_size

    monkeypatch.setattr(hooks, "_plan_limits_provider", None)
    monkeypatch.setattr(settings, "max_batch_size", 50)

    assert await plan_max_batch_size(db_session, object()) == 50


@pytest.mark.asyncio
async def test_vision_batch_cap_rejects_too_many_images(db_session, monkeypatch):
    from app import hooks
    from app.quotas import enforce_vision_batch

    async def provider(db, user):
        return {"vision_batch_max": 1}

    monkeypatch.setattr(hooks, "_plan_limits_provider", provider)

    with pytest.raises(HTTPException) as exc:
        await enforce_vision_batch(db_session, object(), image_count=2)
    assert exc.value.status_code == 422

    await enforce_vision_batch(db_session, object(), image_count=1)
    await enforce_vision_batch(db_session, object(), image_count=0)
