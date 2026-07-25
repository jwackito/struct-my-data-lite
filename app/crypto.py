import json
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken


_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is not None:
        return _fernet

    key = os.environ.get("APP_SECRET_KEY")
    if key:
        _fernet = Fernet(key.encode() if isinstance(key, str) else key)
        return _fernet

    if os.environ.get("SKIP_ENCRYPTION"):
        _fernet = Fernet(Fernet.generate_key())
        return _fernet

    raise RuntimeError(
        "APP_SECRET_KEY environment variable is required for provider config encryption. "
        "Set it to a Fernet-compatible key (generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"). "
        "For local development, you can set SKIP_ENCRYPTION=1 to use an ephemeral key (secrets won't survive restart)."
    )


def encrypt_secrets(data: dict) -> str:
    if not data:
        return "{}"
    f = _get_fernet()
    raw = json.dumps(data, separators=(",", ":"))
    return f.encrypt(raw.encode()).decode()


def decrypt_secrets(token: str) -> dict:
    if not token or token == "{}":
        return {}
    f = _get_fernet()
    try:
        raw = f.decrypt(token.encode())
    except InvalidToken:
        return {}
    return json.loads(raw.decode())


def mask_value(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return "*" * (len(value) - 4) + value[-4:]
