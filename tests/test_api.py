import pytest
from httpx import ASGITransport, AsyncClient

from esnflux.api import build_api
from esnflux.settings import settings


class FakeMonitor:
    def __init__(self):
        self.state = type("State", (), {
            "online": True,
            "players": 3,
            "latency_ms": 42.5,
            "player_names": ["Alex", "Sam", "Steve"],
            "checked_at": "2026-09-13T00:00:00+00:00",
            "error": None,
        })()


class FakeDatabase:
    async def get_recent_samples(self, limit=100):
        return [{
            "checked_at": "2026-09-13T00:00:00+00:00",
            "online": True,
            "players": 3,
            "latency_ms": 42.5,
            "player_names": ["Alex", "Sam", "Steve"],
        }]


@pytest.mark.asyncio
async def test_health_status_and_players_endpoints():
    app = build_api(FakeMonitor(), FakeDatabase())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        health = await client.get("/api/health")
        status = await client.get("/api/smp/status")
        players = await client.get("/api/smp/players")

    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert status.status_code == 200
    assert status.json()["online"] is True
    assert status.json()["players"] == 3
    assert players.json()["count"] == 3
    assert players.json()["players"] == ["Alex", "Sam", "Steve"]


@pytest.mark.asyncio
async def test_history_requires_api_key_when_configured():
    old_key = settings.api_key
    settings.api_key = "secret"
    try:
        app = build_api(FakeMonitor(), FakeDatabase())
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            denied = await client.get("/api/smp/history")
            allowed = await client.get("/api/smp/history", headers={"X-API-Key": "secret"})

        assert denied.status_code == 401
        assert allowed.status_code == 200
    finally:
        settings.api_key = old_key


@pytest.mark.asyncio
async def test_history_limit_is_bounded():
    class RecordingDatabase(FakeDatabase):
        def __init__(self):
            self.last_limit = None

        async def get_recent_samples(self, limit=100):
            self.last_limit = limit
            return []

    database = RecordingDatabase()
    old_key = settings.api_key
    settings.api_key = ""
    try:
        app = build_api(FakeMonitor(), database)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.get("/api/smp/history?limit=9999")
            assert database.last_limit == 500
            await client.get("/api/smp/history?limit=0")
            assert database.last_limit == 1
    finally:
        settings.api_key = old_key
