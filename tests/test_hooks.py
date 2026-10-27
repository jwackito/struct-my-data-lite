"""Tests for the cross-edition hook registries (spec 24).

Lite registers nothing, so every ``run_*`` function must be a no-op. Cloud
editions register callbacks; those run in registration order and exceptions
propagate (D24-7).
"""

import pytest

from app import hooks


@pytest.mark.asyncio
async def test_run_registration_validators_is_noop_by_default(monkeypatch):
    monkeypatch.setattr(hooks, "_registration_validators", [])
    assert await hooks.run_registration_validators(object(), {"email": "a@b.c"}) is None


@pytest.mark.asyncio
async def test_registration_validators_run_in_registration_order(monkeypatch):
    calls = []

    async def first(db, payload):
        calls.append("first")

    async def second(db, payload):
        calls.append("second")

    monkeypatch.setattr(hooks, "_registration_validators", [])
    hooks.register_registration_validator(first)
    hooks.register_registration_validator(second)

    await hooks.run_registration_validators(object(), {"email": "a@b.c"})

    assert calls == ["first", "second"]


@pytest.mark.asyncio
async def test_registration_validator_exception_propagates(monkeypatch):
    async def boom(db, payload):
        raise ValueError("invite required")

    monkeypatch.setattr(hooks, "_registration_validators", [boom])

    with pytest.raises(ValueError, match="invite required"):
        await hooks.run_registration_validators(object(), {})


@pytest.mark.asyncio
async def test_run_job_completion_hooks_is_noop_by_default(monkeypatch):
    monkeypatch.setattr(hooks, "_job_completion_hooks", [])
    assert await hooks.run_job_completion_hooks(object(), object(), None) is None


@pytest.mark.asyncio
async def test_job_completion_hooks_receive_db_job_user(monkeypatch):
    seen = []

    async def hook(db, job, user):
        seen.append((db, job, user))

    db, job, user = object(), object(), object()
    monkeypatch.setattr(hooks, "_job_completion_hooks", [hook])

    await hooks.run_job_completion_hooks(db, job, user)

    assert seen == [(db, job, user)]


@pytest.mark.asyncio
async def test_resolve_plan_limits_returns_none_without_provider(monkeypatch):
    monkeypatch.setattr(hooks, "_plan_limits_provider", None)
    assert await hooks.resolve_plan_limits(object(), object()) is None


@pytest.mark.asyncio
async def test_resolve_plan_limits_returns_provider_value(monkeypatch):
    limits = {"provider_scope": "ollama"}

    async def provider(db, user):
        return limits

    monkeypatch.setattr(hooks, "_plan_limits_provider", None)
    hooks.register_plan_limits_provider(provider)

    assert await hooks.resolve_plan_limits(object(), object()) is limits


@pytest.mark.asyncio
async def test_run_lifespan_hooks_is_noop_by_default(monkeypatch):
    monkeypatch.setattr(hooks, "_lifespan_hooks", [])
    assert await hooks.run_lifespan_hooks(object()) is None


@pytest.mark.asyncio
async def test_lifespan_hooks_receive_app_in_order(monkeypatch):
    calls = []

    async def first(app):
        calls.append("first")

    async def second(app):
        calls.append("second")

    monkeypatch.setattr(hooks, "_lifespan_hooks", [])
    hooks.register_lifespan_hook(first)
    hooks.register_lifespan_hook(second)

    await hooks.run_lifespan_hooks("app")

    assert calls == ["first", "second"]


@pytest.mark.asyncio
async def test_run_job_creation_validators_is_noop_by_default(monkeypatch):
    monkeypatch.setattr(hooks, "_job_creation_validators", [])
    assert await hooks.run_job_creation_validators(object(), object(), "ollama") is None


@pytest.mark.asyncio
async def test_job_creation_validators_receive_arguments(monkeypatch):
    seen = []

    async def validator(db, user, provider_type, new_jobs, estimate_usd):
        seen.append((provider_type, new_jobs, estimate_usd))

    monkeypatch.setattr(hooks, "_job_creation_validators", [validator])

    await hooks.run_job_creation_validators(object(), object(), "openai", 3, 0.25)

    assert seen == [("openai", 3, 0.25)]
