import uuid
from pathlib import Path

STORAGE_DIR = Path("storage")


def save_file(filename: str, content: bytes) -> str:
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    unique_name = f"{uuid.uuid4()}_{filename}"
    path = STORAGE_DIR / unique_name
    path.write_bytes(content)
    return str(path)
