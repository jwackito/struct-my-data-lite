from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.models import ModelRegistry, User, UserModelAccess
from app.providers.base import ModelInfo
from app.providers.factory import list_all_models


class FakeProvider:
    def __init__(self, models):
        self._models = models

    def list_models(self):
        return self._models


def _info(name, caps=None):
    return ModelInfo(id=f"ollama/{name}", provider="ollama", model_name=name, capabilities=caps or ["text"])


@pytest.mark.asyncio
async def test_list_all_models_upserts_registry(async_client, db_session):
    fake = FakeProvider([_info("qwen-test")])
    with patch("app.providers.factory._build_provider", return_value=fake):
        models = await list_all_models(db_session)
    assert [m["model"] for m in models] == ["qwen-test"]
    regs = (await db_session.execute(select(ModelRegistry))).scalars().all()
    assert len(regs) == 1
    assert regs[0].connection_id is None
    assert regs[0].capabilities == ["text"]
    assert regs[0].last_seen_at is not None


@pytest.mark.asyncio
async def test_hidden_disabled_model(async_client, db_session):
    fake = FakeProvider([_info("a"), _info("b")])
    with patch("app.providers.factory._build_provider", return_value=fake):
        await list_all_models(db_session)
    reg = (await db_session.execute(select(ModelRegistry).where(ModelRegistry.model_name == "a"))).scalar_one()
    reg.enabled = False
    await db_session.commit()
    with patch("app.providers.factory._build_provider", return_value=fake):
        models = await list_all_models(db_session)
    assert [m["model"] for m in models] == ["b"]


@pytest.mark.asyncio
async def test_admin_only_visible_to_admin(async_client, db_session):
    fake = FakeProvider([_info("secret-model")])
    with patch("app.providers.factory._build_provider", return_value=fake):
        await list_all_models(db_session)
    reg = (await db_session.execute(select(ModelRegistry))).scalar_one()
    reg.admin_only = True
    await db_session.commit()

    user = User(email="u@example.com", password_hash="x", display_name="u", role="user")
    admin = User(email="a@example.com", password_hash="x", display_name="a", role="admin")
    db_session.add_all([user, admin])
    await db_session.commit()

    with patch("app.providers.factory._build_provider", return_value=fake):
        u_models = await list_all_models(db_session, user=user)
        a_models = await list_all_models(db_session, user=admin)
    assert u_models == []
    assert [m["model"] for m in a_models] == ["secret-model"]


@pytest.mark.asyncio
async def test_deny_hides_and_allow_bypasses_admin_only(async_client, db_session):
    fake = FakeProvider([_info("m1"), _info("m2")])
    with patch("app.providers.factory._build_provider", return_value=fake):
        await list_all_models(db_session)
    regs = (await db_session.execute(select(ModelRegistry))).scalars().all()
    m1 = next(r for r in regs if r.model_name == "m1")
    m2 = next(r for r in regs if r.model_name == "m2")
    m2.admin_only = True
    await db_session.commit()

    user = User(email="u@example.com", password_hash="x", display_name="u", role="user")
    db_session.add(user)
    await db_session.flush()
    db_session.add(UserModelAccess(user_id=user.id, model_id=m1.id, access="deny"))
    db_session.add(UserModelAccess(user_id=user.id, model_id=m2.id, access="allow"))
    await db_session.commit()

    with patch("app.providers.factory._build_provider", return_value=fake):
        models = await list_all_models(db_session, user=user)
    assert [m["model"] for m in models] == ["m2"]


@pytest.mark.asyncio
async def test_embeddings_model_skipped(async_client, db_session):
    fake = FakeProvider([_info("emb", caps=["embeddings"])])
    with patch("app.providers.factory._build_provider", return_value=fake):
        models = await list_all_models(db_session)
    assert models == []


@pytest.mark.asyncio
async def test_order_and_display_fields(async_client, db_session):
    fake = FakeProvider([_info("zeta"), _info("alpha")])
    with patch("app.providers.factory._build_provider", return_value=fake):
        await list_all_models(db_session)
    regs = (await db_session.execute(select(ModelRegistry))).scalars().all()
    alpha = next(r for r in regs if r.model_name == "alpha")
    alpha.sort_order = 1
    alpha.display_name = "Alpha Model"
    alpha.description = "desc"
    alpha.price_input_usd = 1.5
    alpha.price_output_usd = 3.0
    alpha.context_window = 128000
    await db_session.commit()

    with patch("app.providers.factory._build_provider", return_value=fake):
        models = await list_all_models(db_session)
    assert [m["model"] for m in models] == ["zeta", "alpha"]
    entry = models[1]
    assert entry["display_name"] == "Alpha Model"
    assert entry["description"] == "desc"
    assert entry["price_input_usd"] == 1.5
    assert entry["context_window"] == 128000
    assert entry["is_default"] is False