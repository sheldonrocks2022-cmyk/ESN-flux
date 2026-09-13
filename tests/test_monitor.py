from types import SimpleNamespace

import pytest

from esnflux.monitor import SMPMonitor


class FakeDatabase:
    def __init__(self):
        self.samples = []

    async def sample(self, online, players, latency_ms, names):
        self.samples.append((online, players, latency_ms, names))


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
    assert state.latency_ms is not None
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
    assert state.latency_ms is None
    assert "TimeoutError" in state.error
    assert db.samples[-1][0] is False


@pytest.mark.asyncio
async def test_monitor_treats_missing_player_sample_as_unknown(monkeypatch):
    class FakeServer:
        def status(self):
            return SimpleNamespace(players=SimpleNamespace(online=4, sample=[]))

    async def fake_to_thread(func, *args, **kwargs):
        if func.__name__ == "lookup":
            return FakeServer()
        return func(*args, **kwargs)

    monkeypatch.setattr("esnflux.monitor.asyncio.to_thread", fake_to_thread)
    monitor = SMPMonitor("example", 17058, 30, FakeDatabase())
    state = await monitor.probe()

    assert state.online is True
    assert state.players == 4
    assert state.player_names == []


@pytest.mark.asyncio
async def test_monitor_start_is_idempotent(monkeypatch):
    monitor = SMPMonitor("example", 17058, 30, FakeDatabase())

    async def fake_run():
        await asyncio.sleep(60)

    import asyncio
    monkeypatch.setattr(monitor, "run", fake_run)

    await monitor.start()
    first_task = monitor._task
    await monitor.start()

    assert monitor._task is first_task
    await monitor.stop()
    assert monitor._task is None
