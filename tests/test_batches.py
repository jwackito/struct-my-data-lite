import pytest


@pytest.mark.asyncio
async def test_batch_creation_creates_job_per_document(async_client, db_session):
    reg = await async_client.post("/auth/register", json={
        "email": "batch-create@example.com",
        "password": "password123",
    })
    token = reg.json()["token"]

    from app.models import Document
    doc_ids = []
    for i in range(3):
        doc = Document(filename=f"doc{i}.txt", content_type="text/plain", file_size=10, storage_path=f"/tmp/doc{i}.txt")
        db_session.add(doc)
        await db_session.flush()
        doc_ids.append(str(doc.id))
    await db_session.commit()

    resp = await async_client.post("/api/batches", json={
        "document_ids": doc_ids,
        "pydantic_schema": "class X(BaseModel): pass",
        "model_id": "ollama/ollama/qwen3.6:35b",
    }, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "batch_id" in data
    assert len(data["job_ids"]) == 3
