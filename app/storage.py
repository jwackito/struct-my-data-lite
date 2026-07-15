import re
import uuid
from pathlib import Path

STORAGE_DIR = Path("storage")


def sanitize_filename(filename: str) -> str:
    filename = re.sub(r'[\\/:\x00]', '_', filename)
    return filename


def save_file(filename: str, content: bytes) -> str:
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = sanitize_filename(filename)
    unique_name = f"{uuid.uuid4()}_{safe_name}"
    path = STORAGE_DIR / unique_name
    path.write_bytes(content)
    return str(path)
