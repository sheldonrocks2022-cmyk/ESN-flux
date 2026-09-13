from types import SimpleNamespace

import pytest

from esnflux.bot import ESNFluxBot


class FakeDatabase:
    def __init__(self):
        self.incidents = []
        self.resolved = []
        self.sessions = []
        self.closed = []
        self.values = {}

    async def incident_once(self, kind, message):
        self.incidents.append((kind, message))
        return len(self.incidents)

    async def resolve_latest(self, kind):
        self.resolved.append(kind)

    async def open_session(self, name):
        self.sessions.append(name)

    async def close_session(self, name):
        self.closed.append(name)

    async def get_value(self, key, default=None):
        return self.values.get(key, default)

    async def set_value(self, key, value):
        self.values[key] = value


class FakeBot:
    state_changed = ESNFluxBot.state_changed

    def __init__(self):
        self.database = FakeDatabase()
        self.previous_players = set()
        self.previous_online = False
        self.peak = 0
        self.logs = []

    async def send_log(self, embed):
        self.logs.append(embed)


@pytest.mark.asyncio
async def test_offline_transition_creates_one_incident_and_closes_sessions():
    bot = FakeBot()
    bot.previous_players = {"Alex", "Sam"}

    old = SimpleNamespace(online=True, players=2, player_names=["Alex", "Sam"])
    new = SimpleNamespace(online=False, players=0, player_names=[], latency_ms=None, error="timeout")

    await bot.state_changed(old, new)

    assert bot.database.incidents == [("SMP_OFFLINE", "timeout")]
    assert bot.database.closed == ["Alex", "Sam"]
    assert bot.previous_players == set()


@pytest.mark.asyncio
async def test_recovery_resolves_outage_and_tracks_new_players():
    bot = FakeBot()
    bot.previous_players = set()

    old = SimpleNamespace(online=False, players=0, player_names=[])
    new = SimpleNamespace(online=True, players=2, player_names=["Alex", "Sam"], latency_ms=25, error=None)

    await bot.state_changed(old, new)

    assert bot.database.resolved == ["SMP_OFFLINE"]
    assert bot.database.sessions == ["Alex", "Sam"]
    assert bot.previous_players == {"Alex", "Sam"}
    assert bot.peak == 2
    assert bot.database.values["smp_peak"] == "2"


@pytest.mark.asyncio
async def test_missing_player_sample_does_not_close_known_players():
    bot = FakeBot()
    bot.previous_players = {"Alex", "Sam"}

    old = SimpleNamespace(online=True, players=2, player_names=["Alex", "Sam"])
    new = SimpleNamespace(online=True, players=2, player_names=[], latency_ms=20, error=None)

    await bot.state_changed(old, new)

    assert bot.database.closed == []
    assert bot.previous_players == {"Alex", "Sam"}
