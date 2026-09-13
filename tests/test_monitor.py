from types import SimpleNamespace

import pytest

from esnflux.monitor import SMPMonitor


class FakeDatabase:
    def __init__(self):
        self.samples = []

    async def sample(self, online, players, latency_ms, names):
        self.samples.append((online, players, names))


@pytest.mark.asyncio
async def test_monitor_records_online_state(monkeypatch):
    class FakeServer:
        def status(self):
            return SimpleNamespace(
                players=SimpleNamespace(
                    online=2,
                    sample=[SimpleNamespace(name="Alex"), SimpleNamespace(name="Sam")],
                )
            )

    async def fake_to_thread(func, *args, **kwargs):
        if func.__name__ == "lookup":
            return FakeServer()
        return func(*args, **kwargs)

    monkeypatch.setattr("esnflux.monitor.asyncio.to_thread", fake_to_thread)
    db = FakeDatabase()
    monitor = SMPMonitor("example", 17058, 30, db)
    state = await monitor.probe()

    assert state.online is True
    assert state.players == 2
    assert state.player_names == ["Alex", "Sam"]
    assert db.samples[-1][0] is True


@pytest.mark.asyncio
async def test_monitor_handles_probe_failure(monkeypatch):
    async def failing_to_thread(*args, **kwargs):
        raise TimeoutError("server timeout")

    monkeypatch.setattr("esnflux.monitor.asyncio.to_thread", failing_to_thread)
    db = FakeDatabase()
    monitor = SMPMonitor("example", 17058, 30, db)
    state = await monitor.probe()

    assert state.online is False
    assert state.players == 0
    assert "TimeoutError" in state.error
    assert db.samples[-1][0] is False
