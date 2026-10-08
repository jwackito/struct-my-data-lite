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
