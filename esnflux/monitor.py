from dataclasses import dataclass, field
import asyncio
import time
from mcstatus import BedrockServer


@dataclass
class SMPState:
    online: bool = False
    players: int = 0
    player_names: list[str] = field(default_factory=list)
    player_names_available: bool = False
    latency_ms: float | None = None
    checked_at: float = 0.0
    error: str | None = None


class SMPMonitor:
    def __init__(self, host: str, port: int, interval: int, database, on_change=None):
        self.host = host
        self.port = port
        self.interval = interval
        self.database = database
        self.on_change = on_change
        self.state = SMPState()
        self._running = False
        self._task = None

    async def probe(self):
        started = time.perf_counter()
        try:
            server = await asyncio.to_thread(BedrockServer.lookup, f"{self.host}:{self.port}")
            status = await asyncio.to_thread(server.status)
            latency = (time.perf_counter() - started) * 1000
            players = getattr(status, "players", None)
            if players is None:
                players_online = 0
                names = []
                names_available = False
            else:
                players_online = int(getattr(players, "online", 0) or 0)
                sample = getattr(players, "sample", None)
                names = [getattr(player, "name", str(player)) for player in (sample or []) if player]
                names_available = sample is not None or players_online == 0

            new_state = SMPState(
                online=True,
                players=players_online,
                player_names=names,
                player_names_available=names_available,
                latency_ms=latency,
                checked_at=time.time(),
                error=None,
            )
        except Exception as exc:
            new_state = SMPState(
                online=False,
                players=0,
                player_names=[],
                player_names_available=False,
                latency_ms=None,
                checked_at=time.time(),
                error=f"{type(exc).__name__}: {exc}",
            )

        previous = self.state
        self.state = new_state
        await self.database.sample(new_state.online, new_state.players, new_state.latency_ms, new_state.player_names)
        if self.on_change:
            await self.on_change(previous, new_state)
        return new_state

    async def run(self):
        self._running = True
        while self._running:
            try:
                await self.probe()
            except asyncio.CancelledError:
                raise
            except Exception:
                # A persistence/callback failure must not kill the monitor loop.
                # The next interval retries the complete probe and persistence path.
                pass
            await asyncio.sleep(self.interval)

    async def start(self):
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self.run(), name="esnflux-smp-monitor")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
