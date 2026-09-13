from dataclasses import dataclass, field
import asyncio
import time
import httpx


DEFAULT_PATHS = (
    "/",
    "/smp",
    "/estowerdefense",
    "/esclicker",
    "/esfactory",
    "/esmoto",
    "/esmines",
    "/estools",
    "/estower",
    "/api/health",
    "/api/smp/status",
    "/api/smp/players",
    "/api/smp/history",
)


@dataclass
class WebsiteResult:
    path: str
    url: str
    available: bool
    status_code: int | None = None
    response_ms: float | None = None
    error: str | None = None
    checked_at: float = field(default_factory=time.time)


class WebsiteMonitor:
    def __init__(self, base_url: str, interval: int, database, on_change=None):
        self.base_url = base_url.rstrip("/")
        self.interval = interval
        self.database = database
        self.on_change = on_change
        self.results: dict[str, WebsiteResult] = {}
        self._running = False
        self._task = None

    async def probe_path(self, client: httpx.AsyncClient, path: str):
        url = f"{self.base_url}{path}"
        started = time.perf_counter()
        try:
            response = await client.get(url, follow_redirects=True)
            elapsed = (time.perf_counter() - started) * 1000
            result = WebsiteResult(
                path=path,
                url=url,
                available=200 <= response.status_code < 400,
                status_code=response.status_code,
                response_ms=elapsed,
                error=None if response.status_code < 400 else f"HTTP {response.status_code}",
            )
        except Exception as exc:
            result = WebsiteResult(
                path=path,
                url=url,
                available=False,
                response_ms=(time.perf_counter() - started) * 1000,
                error=f"{type(exc).__name__}: {exc}",
            )
        await self.database.record_website_sample(result)
        return result

    async def probe(self):
        async with httpx.AsyncClient(timeout=15, headers={"User-Agent": "ESNFlux/WebsiteMonitor"}) as client:
            results = await asyncio.gather(*(self.probe_path(client, path) for path in DEFAULT_PATHS))
        previous = self.results
        self.results = {result.path: result for result in results}
        for result in results:
            old = previous.get(result.path)
            if old is None or old.available != result.available:
                kind = "WEBSITE_DOWN" if not result.available else "WEBSITE_RESTORED"
                message = f"{result.path} — {result.error or 'available'}"
                if not result.available:
                    await self.database.incident_once(kind, message)
                else:
                    await self.database.resolve_latest("WEBSITE_DOWN")
        if self.on_change:
            await self.on_change(previous, self.results)
        return self.results

    async def run(self):
        self._running = True
        while self._running:
            try:
                await self.probe()
            except asyncio.CancelledError:
                raise
            except Exception:
                pass
            await asyncio.sleep(self.interval)

    async def start(self):
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self.run(), name="esnflux-website-monitor")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
