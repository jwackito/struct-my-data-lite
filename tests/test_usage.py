import pytest

from app.pricing import calculate_cost


def test_cost_known_model():
    cost = calculate_cost("openai", "gpt-4o-mini", 1000, 500)
    # 1000 * 0.15 / 1M + 500 * 0.60 / 1M = 0.00015 + 0.00030 = 0.00045
    assert cost == pytest.approx(0.00045, rel=1e-3)


def test_cost_ollama_free():
    cost = calculate_cost("ollama", "qwen3.6:35b", 10000, 5000)
    assert cost == 0.0


def test_cost_prefix_match():
    cost = calculate_cost("openai", "gpt-4o-2024-08-06", 1000, 500)
    # Uses gpt-4o pricing: 1000 * 2.50 / 1M + 500 * 10.00 / 1M = 0.0025 + 0.005 = 0.0075
    assert cost == pytest.approx(0.0075, rel=1e-3)


def test_cost_unknown_model():
    cost = calculate_cost("openai", "some-random-model", 1000, 500)
    assert cost == 0.0


def test_cost_unknown_provider():
    cost = calculate_cost("nonexistent", "model", 1000, 500)
    assert cost == 0.0


@pytest.mark.asyncio
async def test_usage_with_jobs(async_client, db_session):
    reg = await async_client.post("/auth/register", json={
        "email": "usage-jobs@example.com",
        "password": "password123",
    })
    assert reg.status_code == 200
    user_id = reg.json()["user"]["id"]
    token = reg.json()["token"]

    from app.models import Document, ExtractionJob
    doc = Document(
        user_id=user_id,
        filename="test.txt", content_type="text/plain",
        file_size=10, storage_path="/tmp/test.txt",
    )
    db_session.add(doc)
    await db_session.flush()

    job = ExtractionJob(
        user_id=user_id,
        document_id=doc.id,
        status="completed",
        pydantic_schema="class X(BaseModel): pass",
        input_tokens=1000,
        output_tokens=500,
        model_name="gpt-4o-mini",
        provider_type="openai",
    )
    db_session.add(job)
    await db_session.commit()

    resp = await async_client.get("/api/usage", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_jobs"] == 1
    assert data["total_input_tokens"] == 1000
    assert data["total_output_tokens"] == 500
    assert data["total_cost"] > 0


@pytest.mark.asyncio
async def test_usage_with_date_filter(async_client, db_session):
    reg = await async_client.post("/auth/register", json={
        "email": "usage-date@example.com",
        "password": "password123",
    })
    token = reg.json()["token"]
    user_id = reg.json()["user"]["id"]

    from app.models import Document, ExtractionJob
    doc = Document(user_id=user_id, filename="t.txt", content_type="text/plain", file_size=1, storage_path="/tmp/t.txt")
    db_session.add(doc)
    await db_session.flush()
    job = ExtractionJob(user_id=user_id, document_id=doc.id, status="completed",
                        pydantic_schema="class X: pass", input_tokens=10, output_tokens=5,
                        model_name="gpt-4o-mini", provider_type="openai")
    db_session.add(job)
    await db_session.commit()

    resp = await async_client.get("/api/usage?from_date=2020-01-01", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_jobs"] == 1


@pytest.mark.asyncio
async def test_api_usage(async_client):
    reg = await async_client.post("/auth/register", json={
        "email": "usage-test@example.com",
        "password": "password123",
    })
    assert reg.status_code == 200
    token = reg.json()["token"]

    resp = await async_client.get("/api/usage", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "total_jobs" in data
    assert "total_input_tokens" in data
    assert "total_output_tokens" in data
    assert "total_cost" in data


@pytest.mark.asyncio
async def test_admin_usage_data(async_client, db_session):
    reg = await async_client.post("/auth/register", json={
        "email": "admin-usage-tester@example.com",
        "password": "password123",
    })
    assert reg.status_code == 200
    user_id = reg.json()["user"]["id"]
    token = reg.json()["token"]

    from app.models import User
    from sqlalchemy import select
    u = (await db_session.execute(select(User).where(User.email == "admin-usage-tester@example.com"))).scalar_one()
    u.role = "admin"
    await db_session.commit()

    resp = await async_client.get("/admin/usage/data", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "total_users" in data
    assert "total_jobs" in data
    assert "per_user" in data
