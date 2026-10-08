from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connections import get_connection, list_connections
from app.config import settings
from app.i18n import t_req
from app.models import ModelRegistry, User, UserModelAccess
from app.providers.base import LLMProvider, ModelInfo
from app.providers.gemini import GeminiProvider
from app.providers.ollama import OllamaProvider
from app.providers.openai import OpenAIProvider


def _build_provider(provider: str, config: dict) -> LLMProvider:
    if provider == "ollama":
        return OllamaProvider(
            host=config.get("host", settings.ollama_host),
            model=config.get("model", settings.ollama_model),
            vision_model=config.get("vision_model", settings.ollama_vision_model),
        )
    if provider == "openai":
        return OpenAIProvider(
            api_key=config.get("api_key", ""),
            base_url=config.get("base_url", ""),
        )
    if provider == "gemini":
        return GeminiProvider(
            api_key=config.get("api_key", ""),
            model=config.get("model", ""),
        )
    raise ValueError(f"Unknown provider: {provider}")


async def get_provider(connection: str, db: AsyncSession, user: User | None = None) -> LLMProvider:
    if user:
        conn = await get_connection(connection, db, user=user)
        if conn and conn.get("user_id"):
            return _build_provider(conn["provider"], conn["config"])

    conn = await get_connection(connection, db)
    if not conn:
        raise ValueError(f"Provider connection '{connection}' not found")
    return _build_provider(conn["provider"], conn["config"])


async def _sync_registry(db: AsyncSession, conn: dict, provider: LLMProvider, models: list[ModelInfo]) -> None:
    result = await db.execute(
        select(ModelRegistry).where(ModelRegistry.connection_id == conn.get("id"))
    )
    existing = {r.model_name: r for r in result.scalars().all()}
    now = datetime.now(timezone.utc)
    for m in models:
        reg = existing.get(m.model_name)
        if reg is None:
            db.add(ModelRegistry(
                connection_id=conn.get("id"),
                model_name=m.model_name,
                capabilities=m.capabilities,
                last_seen_at=now,
            ))
        else:
            reg.last_seen_at = now
            if reg.capabilities is None:
                reg.capabilities = m.capabilities
    await db.flush()


async def list_all_models(db: AsyncSession, user: User | None = None) -> list[dict]:
    seen = set()
    results = []

    all_conns = await list_connections(db)
    if user:
        personal = await list_connections(db, user=user)
        all_conns.extend(pc for pc in personal if pc["name"] not in {c["name"] for c in all_conns})

    grants = {}
    is_admin = bool(user and user.role == "admin")
    if user:
        res = await db.execute(select(UserModelAccess).where(UserModelAccess.user_id == user.id))
        grants = {a.model_id: a.access for a in res.scalars().all()}

    for conn in all_conns:
        if not conn["enabled"]:
            continue
        conn_user = user if conn.get("user_id") else None
        full = await get_connection(conn["name"], db, user=conn_user)
        if not full:
            continue
        try:
            provider = _build_provider(full["provider"], full["config"])
        except Exception:
            continue

        await _sync_registry(db, conn, provider, provider.list_models())

        result = await db.execute(
            select(ModelRegistry)
            .where(ModelRegistry.connection_id == conn.get("id"))
            .order_by(ModelRegistry.sort_order, ModelRegistry.model_name)
        )
        regs = result.scalars().all()
        for reg in regs:
            caps = reg.capabilities or []
            if caps == ["embeddings"]:
                continue
            access = grants.get(reg.id)
            if not reg.enabled or access == "deny":
                continue
            if not is_admin and access != "allow" and reg.admin_only:
                continue
            model_id = f"{conn['provider']}/{conn['name']}/{reg.model_name}"
            if model_id in seen:
                continue
            seen.add(model_id)
            results.append({
                "id": model_id,
                "provider": conn["provider"],
                "connection": conn["name"],
                "model": reg.model_name,
                "display_name": reg.display_name or reg.model_name,
                "description": reg.description or "",
                "capabilities": caps,
                "context_window": reg.context_window,
                "price_input_usd": reg.price_input_usd,
                "price_output_usd": reg.price_output_usd,
                "is_default": reg.is_default,
            })

    await db.commit()
    return results


async def _parse_model_id(model_id: str, db: AsyncSession | None = None) -> tuple[str, str, str | None]:
    if not model_id:
        if db is not None:
            result = await db.execute(
                select(ModelRegistry).where(
                    ModelRegistry.connection_id.is_(None),
                    ModelRegistry.is_default.is_(True),
                )
            )
            reg = result.scalar_one_or_none()
            if reg:
                return "ollama", "ollama", reg.model_name
        return "ollama", "ollama", settings.ollama_model
    parts = model_id.split("/", 2)
    if len(parts) == 3:
        provider_type, connection_name, model_name = parts
        return provider_type, connection_name, model_name
    if len(parts) == 2:
        provider_type, model_name = parts
        return provider_type, provider_type, model_name
    return model_id, model_id, None


async def authorize_model(db: AsyncSession, user: User, model_id: str) -> tuple[str, str, str | None]:
    """Enforce model access for job creation.

    Resolves a connection visible to the caller (their own or a global one),
    then applies the registry's enabled/admin_only flags and per-user grants.
    A model with no registry row is allowed (D18-14). Raises HTTP 403 on denial.
    """
    provider_type, connection_name, model_name = await _parse_model_id(model_id, db)

    conn = await get_connection(connection_name, db, user=user)
    if not conn:
        conn = await get_connection(connection_name, db)
    if not conn or not conn.get("enabled", True):
        raise HTTPException(status_code=403, detail=t_req("Model not available"))

    result = await db.execute(
        select(ModelRegistry).where(
            ModelRegistry.connection_id == conn.get("id"),
            ModelRegistry.model_name == model_name,
        )
    )
    reg = result.scalar_one_or_none()
    if reg is not None:
        if not reg.enabled:
            raise HTTPException(status_code=403, detail=t_req("Model not available"))
        is_admin = user.role == "admin"
        access = None
        grant = await db.execute(
            select(UserModelAccess).where(
                UserModelAccess.user_id == user.id,
                UserModelAccess.model_id == reg.id,
            )
        )
        row = grant.scalar_one_or_none()
        if row:
            access = row.access
        if access == "deny":
            raise HTTPException(status_code=403, detail=t_req("Model not available"))
        if reg.admin_only and not is_admin and access != "allow":
            raise HTTPException(status_code=403, detail=t_req("Model not available"))

    return provider_type, connection_name, model_name