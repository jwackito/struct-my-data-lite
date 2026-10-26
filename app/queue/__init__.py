"""Queue backend factory (spec 25).

`inprocess` is shared. `arq` lives in the cloud-only `app.queue.arq_backend`
module, resolved by name so lite never ships or imports arq.
"""

import importlib

from app.config import settings
from app.queue.base import JobQueueBackend, QueueFull
from app.queue.inprocess import InProcessQueue

_inprocess = InProcessQueue()

__all__ = ["JobQueueBackend", "QueueFull", "get_backend"]


def get_backend() -> JobQueueBackend:
    backend = settings.queue_backend
    if backend == "inprocess":
        return _inprocess
    if backend == "arq":
        try:
            module = importlib.import_module("app.queue.arq_backend")
        except ModuleNotFoundError as exc:
            if exc.name != "app.queue.arq_backend":
                raise
            raise RuntimeError(
                "queue_backend=arq requires the cloud edition "
                "(app/queue/arq_backend.py is not part of lite)"
            ) from exc
        return module.ArqQueue()
    raise RuntimeError(f"Unknown queue backend: {backend!r}")
