"""Hook registries for edition-specific behaviour (spec 24).

Shared code calls the ``run_*`` / ``resolve_*`` functions unconditionally. Lite
registers nothing, so every call is a no-op; cloud editions register callbacks
from ``app.saas``.

Callbacks run in registration order and their exceptions propagate (D24-7): a
broken edition hook must fail loudly instead of being swallowed.
"""

from typing import Any, Awaitable, Callable

RegistrationValidator = Callable[[Any, dict], Awaitable[None]]
JobCreationValidator = Callable[[Any, Any, str, int, float | None], Awaitable[None]]
JobCompletionHook = Callable[[Any, Any, Any], Awaitable[None]]
PlanLimitsProvider = Callable[[Any, Any], Awaitable[dict | None]]
LifespanHook = Callable[[Any], Awaitable[None]]

_registration_validators: list[RegistrationValidator] = []
_job_creation_validators: list[JobCreationValidator] = []
_job_completion_hooks: list[JobCompletionHook] = []
_plan_limits_provider: PlanLimitsProvider | None = None
_lifespan_hooks: list[LifespanHook] = []


def register_registration_validator(fn: RegistrationValidator) -> None:
    """Validate a registration attempt before the user row is created."""
    _registration_validators.append(fn)


async def run_registration_validators(db: Any, payload: dict) -> None:
    for fn in _registration_validators:
        await fn(db, payload)


def register_job_creation_validator(fn: JobCreationValidator) -> None:
    """Veto job creation (e.g. insufficient balance) before the rows are queued."""
    _job_creation_validators.append(fn)


async def run_job_creation_validators(
    db: Any,
    user: Any,
    provider_type: str,
    new_jobs: int = 1,
    estimate_usd: float | None = None,
) -> None:
    for fn in _job_creation_validators:
        await fn(db, user, provider_type, new_jobs, estimate_usd)


def register_job_completion_hook(fn: JobCompletionHook) -> None:
    """Run on every finished job, before the final commit (completed or failed).

    Raising from a hook skips that commit, leaving the job ``running``.
    """
    _job_completion_hooks.append(fn)


async def run_job_completion_hooks(db: Any, job: Any, user: Any) -> None:
    for fn in _job_completion_hooks:
        await fn(db, job, user)


def register_plan_limits_provider(fn: PlanLimitsProvider) -> None:
    """Set the plan-limits provider; re-registering replaces the previous one."""
    global _plan_limits_provider
    _plan_limits_provider = fn


async def resolve_plan_limits(db: Any, user: Any) -> dict | None:
    """Return the user's plan limits, or ``None`` when no provider is registered."""
    if _plan_limits_provider is None:
        return None
    return await _plan_limits_provider(db, user)


def register_lifespan_hook(fn: LifespanHook) -> None:
    """Run at application startup (Sentry init, logging, subscribers, ...)."""
    _lifespan_hooks.append(fn)


async def run_lifespan_hooks(app: Any) -> None:
    for fn in _lifespan_hooks:
        await fn(app)
