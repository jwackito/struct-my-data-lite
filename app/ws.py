import uuid

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.active: dict[uuid.UUID, list[WebSocket]] = {}

    async def connect(self, job_id: uuid.UUID, ws: WebSocket):
        await ws.accept()
        self.active.setdefault(job_id, []).append(ws)

    def disconnect(self, job_id: uuid.UUID, ws: WebSocket):
        self.active.get(job_id, []).remove(ws)
        if not self.active.get(job_id):
            self.active.pop(job_id, None)

    async def notify(self, job_id: uuid.UUID, data: dict):
        for ws in self.active.get(job_id, []):
            await ws.send_json(data)


manager = ConnectionManager()
