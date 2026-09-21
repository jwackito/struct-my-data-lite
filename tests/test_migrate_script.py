import asyncio

import pytest
from sqlalchemy import text

from scripts import migrate


@pytest.mark.asyncio
async def test_migrate_takes_and_releases_advisory_lock(monkeypatch):
    calls = []

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def execute(self, stmt, params=None):
            calls.append(str(stmt))

    class FakeProc:
        returncode = 0

        async def wait(self):
            return 0

    async def fake_exec(*args, **kwargs):
        return FakeProc()

    monkeypatch.setattr(migrate, "async_session", lambda: FakeSession())
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

    code = await migrate.run()

    assert code == 0
    assert any("pg_advisory_lock" in c for c in calls)
    assert any("pg_advisory_unlock" in c for c in calls)
