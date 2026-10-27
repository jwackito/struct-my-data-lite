import pytest
from fastapi import HTTPException

from app.models import ModelRegistry, User
from app.providers.factory import authorize_model


@pytest.mark.asyncio
async def test_authorize_model_allows_valid_global_model(db_session):
    user = User(email="u@example.com", password_hash="x", display_name="u", role="user")
    db_session.add(user)
    await db_session.commit()
    db_session.add(ModelRegistry(connection_id=None, model_name="qwen-test", enabled=True))
    await db_session.commit()

    result = await authorize_model(db_session, user, "ollama/ollama/qwen-test")
    assert result == ("ollama", "ollama", "qwen-test")


@pytest.mark.asyncio
async def test_authorize_model_rejects_admin_only_for_user(db_session):
    user = User(email="u@example.com", password_hash="x", display_name="u", role="user")
    db_session.add(user)
    await db_session.commit()
    db_session.add(ModelRegistry(connection_id=None, model_name="secret", enabled=True, admin_only=True))
    await db_session.commit()

    with pytest.raises(HTTPException) as exc:
        await authorize_model(db_session, user, "ollama/ollama/secret")
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_authorize_model_rejects_deny_grant(db_session):
    from app.models import UserModelAccess

    user = User(email="u@example.com", password_hash="x", display_name="u", role="user")
    db_session.add(user)
    await db_session.commit()
    reg = ModelRegistry(connection_id=None, model_name="blocked", enabled=True)
    db_session.add(reg)
    await db_session.commit()
    db_session.add(UserModelAccess(user_id=user.id, model_id=reg.id, access="deny"))
    await db_session.commit()

    with pytest.raises(HTTPException) as exc:
        await authorize_model(db_session, user, "ollama/ollama/blocked")
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_authorize_model_allow_grant_bypasses_admin_only(db_session):
    from app.models import UserModelAccess

    user = User(email="u@example.com", password_hash="x", display_name="u", role="user")
    db_session.add(user)
    await db_session.commit()
    reg = ModelRegistry(connection_id=None, model_name="premium", enabled=True, admin_only=True)
    db_session.add(reg)
    await db_session.commit()
    db_session.add(UserModelAccess(user_id=user.id, model_id=reg.id, access="allow"))
    await db_session.commit()

    result = await authorize_model(db_session, user, "ollama/ollama/premium")
    assert result == ("ollama", "ollama", "premium")


@pytest.mark.asyncio
async def test_authorize_model_admin_bypasses_admin_only(db_session):
    admin = User(email="a@example.com", password_hash="x", display_name="a", role="admin")
    db_session.add(admin)
    await db_session.commit()
    db_session.add(ModelRegistry(connection_id=None, model_name="secret", enabled=True, admin_only=True))
    await db_session.commit()

    result = await authorize_model(db_session, admin, "ollama/ollama/secret")
    assert result == ("ollama", "ollama", "secret")


@pytest.mark.asyncio
async def test_authorize_model_allows_missing_registry_row(db_session):
    user = User(email="u@example.com", password_hash="x", display_name="u", role="user")
    db_session.add(user)
    await db_session.commit()

    result = await authorize_model(db_session, user, "ollama/ollama/never-synced")
    assert result == ("ollama", "ollama", "never-synced")


@pytest.mark.asyncio
async def test_authorize_model_rejects_disabled_registry_row(db_session):
    user = User(email="u@example.com", password_hash="x", display_name="u", role="user")
    db_session.add(user)
    await db_session.commit()
    db_session.add(ModelRegistry(connection_id=None, model_name="off", enabled=False))
    await db_session.commit()

    with pytest.raises(HTTPException) as exc:
        await authorize_model(db_session, user, "ollama/ollama/off")
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_authorize_model_rejects_foreign_personal_connection(db_session):
    from app.models import LLMConnection

    alice = User(email="alice@example.com", password_hash="x", display_name="alice", role="user")
    bob = User(email="bob@example.com", password_hash="x", display_name="bob", role="user")
    db_session.add_all([alice, bob])
    await db_session.commit()
    db_session.add(LLMConnection(name="bob-key", provider="openai", user_id=bob.id, config={}, secrets="{}"))
    await db_session.commit()

    with pytest.raises(HTTPException) as exc:
        await authorize_model(db_session, alice, "openai/bob-key/gpt-4o")
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_plan_provider_scope_blocks_non_ollama(db_session, monkeypatch):
    from app import hooks

    async def provider(db, user):
        return {"provider_scope": "ollama"}

    monkeypatch.setattr(hooks, "_plan_limits_provider", provider)
    user = User(email="u@example.com", password_hash="x", display_name="u", role="user")
    db_session.add(user)
    await db_session.commit()

    with pytest.raises(HTTPException) as exc:
        await authorize_model(db_session, user, "openai/gpt-4o")
    assert exc.value.status_code == 403
    assert "local models" in exc.value.detail


@pytest.mark.asyncio
async def test_plan_provider_scope_allows_ollama(db_session, monkeypatch):
    from app import hooks

    async def provider(db, user):
        return {"provider_scope": "ollama"}

    monkeypatch.setattr(hooks, "_plan_limits_provider", provider)
    user = User(email="u@example.com", password_hash="x", display_name="u", role="user")
    db_session.add(user)
    await db_session.commit()
    db_session.add(ModelRegistry(connection_id=None, model_name="qwen-test", enabled=True))
    await db_session.commit()

    assert await authorize_model(db_session, user, "ollama/ollama/qwen-test") == (
        "ollama",
        "ollama",
        "qwen-test",
    )
