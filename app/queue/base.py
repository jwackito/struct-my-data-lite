"""Queue backend interface (spec 25).

Shared code talks to a backend instead of scheduling work directly. Lite uses
the in-process backend; cloud resolves `app.queue.arq_backend` by name.
"""

from typing import Protocol

from fastapi import BackgroundTasks


class QueueFull(Exception):
    """The backend cannot accept more jobs right now.

    The web layer translates this into a localized `503` so the queue layer
    never depends on FastAPI's HTTP exceptions.
    """


class JobQueueBackend(Protocol):
    async def enqueue(self, background_tasks: BackgroundTasks, job_ids: list) -> None:
        """Take ownership of pending jobs, or raise `QueueFull`."""
