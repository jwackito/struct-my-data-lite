import uuid

import pytest

from app.storage import sanitize_filename


def test_sanitize_filename_removes_path_separators():
    assert sanitize_filename("/etc/passwd") == "_etc_passwd"
    assert sanitize_filename("../foo/bar.txt") == ".._foo_bar.txt"


def test_sanitize_filename_removes_null_bytes():
    assert sanitize_filename("file\x00.txt") == "file_.txt"


def test_sanitize_filename_preserves_safe_names():
    assert sanitize_filename("hello.txt") == "hello.txt"
    assert sanitize_filename("my_document (1).pdf") == "my_document (1).pdf"


@pytest.mark.asyncio
async def test_extract_missing_document_id(async_client):
    await async_client.post("/auth/register", json={
        "email": "extract1@example.com",
        "password": "password123",
    })
    response = await async_client.post(
        "/extract",
        json={"document_id": str(uuid.uuid4()), "pydantic_schema": "from pydantic import BaseModel\nclass X(BaseModel):\n    y: str"},
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_extract_without_document_id(async_client):
    await async_client.post("/auth/register", json={
        "email": "extract2@example.com",
        "password": "password123",
    })
    response = await async_client.post("/extract", json={"pydantic_schema": "..."})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_extract_oversized_schema(async_client):
    await async_client.post("/auth/register", json={
        "email": "extract3@example.com",
        "password": "password123",
    })
    big_schema = "x" * 10001
    response = await async_client.post(
        "/extract",
        json={"document_id": str(uuid.uuid4()), "pydantic_schema": big_schema},
    )
    assert response.status_code == 422
