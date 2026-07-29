import json
import urllib.request
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.crypto import decrypt_secrets, encrypt_secrets, mask_value
from app.models import LLMConnection


def get_implicit_ollama() -> dict:
    return {
        "name": "ollama",
        "provider": "ollama",
        "config": {
            "host": settings.ollama_host,
            "model": settings.ollama_model,
            "vision_model": settings.ollama_vision_model,
        },
        "enabled": True,
    }


async def list_connections(db: AsyncSession) -> list[dict]:
    implicit = get_implicit_ollama()
    implicit["available"] = _probe_ollama(implicit["config"]["host"])

    result = await db.execute(select(LLMConnection).order_by(LLMConnection.created_at))
    rows = result.scalars().all()

    named = []
    for row in rows:
        secrets = decrypt_secrets(row.secrets)
        named.append({
            "name": row.name,
            "provider": row.provider,
            "config": _mask_config(row.provider, row.config, secrets),
            "enabled": row.enabled,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        })

    return [implicit] + named


async def get_connection(name: str, db: AsyncSession) -> dict | None:
    if name == "ollama":
        return get_implicit_ollama()

    result = await db.execute(select(LLMConnection).where(LLMConnection.name == name))
    row = result.scalar_one_or_none()
    if not row:
        return None

    secrets = decrypt_secrets(row.secrets)
    return {
        "name": row.name,
        "provider": row.provider,
        "config": {**row.config, **secrets},
        "enabled": row.enabled,
    }


async def set_connection(name: str, provider: str, config: dict, secrets: dict, db: AsyncSession) -> dict:
    if name == "ollama":
        raise ValueError("Cannot modify the implicit ollama connection")

    encrypted = encrypt_secrets(secrets)

    result = await db.execute(select(LLMConnection).where(LLMConnection.name == name))
    row = result.scalar_one_or_none()

    if row:
        row.config = config
        row.secrets = encrypted
        row.provider = provider
        row.updated_at = datetime.now(timezone.utc)
    else:
        row = LLMConnection(name=name, provider=provider, config=config, secrets=encrypted)
        db.add(row)

    await db.commit()
    await db.refresh(row)

    decrypted = decrypt_secrets(row.secrets)
    return {
        "name": row.name,
        "provider": row.provider,
        "config": _mask_config(row.provider, row.config, decrypted),
        "enabled": row.enabled,
    }


async def delete_connection(name: str, db: AsyncSession) -> bool:
    if name == "ollama":
        raise ValueError("Cannot delete the implicit ollama connection")

    result = await db.execute(select(LLMConnection).where(LLMConnection.name == name))
    row = result.scalar_one_or_none()
    if not row:
        return False

    await db.delete(row)
    await db.commit()
    return True


async def test_connection(name: str, config: dict, provider: str, db: AsyncSession) -> dict:
    from app.providers.factory import _build_provider

    try:
        if provider == "openai":
            _verify_openai_connectivity(config)
        elif provider == "gemini":
            _verify_gemini_connectivity(config)

        prov = _build_provider(provider, config)
        models = prov.list_models()
        return {"ok": True, "models": [m.id for m in models]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _verify_openai_connectivity(config: dict):
    api_key = config.get("api_key", "")
    if not api_key:
        raise ValueError("API key is required for OpenAI connection test")
    headers = {"Authorization": f"Bearer {api_key}"}
    base_url = config.get("base_url", "").rstrip("/")
    url = f"{base_url}/models" if base_url else "https://api.openai.com/v1/models"
    req = urllib.request.Request(url, headers=headers)
    urllib.request.urlopen(req, timeout=10)


def _verify_gemini_connectivity(config: dict):
    import urllib.parse

    api_key = config.get("api_key", "")
    if not api_key:
        raise ValueError("API key is required for Gemini connection test")
    params = urllib.parse.urlencode({"key": api_key})
    url = f"https://generativelanguage.googleapis.com/v1/models?{params}"
    urllib.request.urlopen(urllib.request.Request(url), timeout=10)


def _probe_ollama(host: str) -> bool:
    try:
        req = urllib.request.Request(f"{host}/api/tags")
        urllib.request.urlopen(req, timeout=3)
        return True
    except Exception:
        return False


def _mask_config(provider: str, config: dict, secrets: dict) -> dict:
    masked = dict(config)
    secret_keys = {"api_key"}
    for key in secret_keys:
        if key in secrets:
            masked[key] = mask_value(secrets[key])
        elif key in masked:
            masked[key] = mask_value(masked[key])
    return masked
