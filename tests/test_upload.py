import pytest
from app.config import settings
from app.storage import save_file


def test_save_file(tmp_path, monkeypatch):
    monkeypatch.setattr("app.storage.STORAGE_DIR", tmp_path)
    path = save_file("hello.txt", b"hello world")
    assert (tmp_path / path).read_bytes() == b"hello world"
    assert "hello.txt" in path


def test_save_file_sanitizes_filename(tmp_path, monkeypatch):
    monkeypatch.setattr("app.storage.STORAGE_DIR", tmp_path)
    path = save_file("../../malicious.txt", b"data")
    stored = tmp_path / path
    assert stored.parent == tmp_path
    assert stored.read_bytes() == b"data"


@pytest.mark.asyncio
async def test_upload_too_large(async_client):
    await async_client.post("/auth/register", json={
        "email": "upload@example.com",
        "password": "password123",
    })
    max_size = settings.max_upload_size
    response = await async_client.post(
        "/upload",
        files={"file": ("big.bin", b"x" * (max_size + 1))},
    )
    assert response.status_code == 413
    assert "exceeds" in response.json()["detail"]
