import pytest
from httpx import ASGITransport, AsyncClient

from esnflux.api import build_api


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
        return [{"checked_at": "2026-09-13T00:00:00+00:00", "online": True, "players": 3, "latency_ms": 42.5, "player_names": ["Alex", "Sam", "Steve"]}]


@pytest.mark.asyncio
async def test_health_and_status_endpoints():
    app = build_api(FakeMonitor(), FakeDatabase())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        health = await client.get("/api/health")
        status = await client.get("/api/smp/status")

    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert status.status_code == 200
    assert status.json()["online"] is True
    assert status.json()["players"] == 3


@pytest.mark.asyncio
async def test_history_requires_api_key_when_configured(monkeypatch):
    monkeypatch.setenv("API_KEY", "secret")
    app = build_api(FakeMonitor(), FakeDatabase())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        denied = await client.get("/api/smp/history")

    assert denied.status_code == 401
