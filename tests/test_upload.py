import pytest
from app.config import settings
from app.storage import save_file


def test_save_file(tmp_path, monkeypatch):
    monkeypatch.setattr("app.storage.STORAGE_DIR", tmp_path)
    path = save_file("hello.txt", b"hello world")
    assert (tmp_path / path).read_bytes() == b"hello world"
    assert "hello.txt" in path


@pytest.mark.asyncio
async def test_upload_too_large(client):
    max_size = settings.max_upload_size
    response = await client.post(
        "/upload",
        files={"file": ("big.bin", b"x" * (max_size + 1))},
    )
    assert response.status_code == 413
    assert "exceeds" in response.json()["detail"]
