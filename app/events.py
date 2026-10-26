"""Job event fan-out (spec 25).

Every job status change goes through `publish_job_update`. In-process backends
only reach local WebSocket clients; cloud registers a publisher that forwards
the event to Redis so a worker process can reach the app's clients.
"""

import uuid

from app.ws import manager

_publisher = None


def set_publisher(fn) -> None:
    """Register an async publisher called before the local notify."""
    global _publisher
    _publisher = fn


async def publish_job_update(payload: dict) -> None:
    if _publisher is not None:
        await _publisher(payload)
    await manager.notify(uuid.UUID(payload["job_id"]), payload)
