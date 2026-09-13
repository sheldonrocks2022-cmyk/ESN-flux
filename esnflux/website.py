from dataclasses import dataclass, field
import time


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
    def __init__(self, base_url: str, interval: int, database, crawler=None, on_change=None):
        self.base_url = base_url.rstrip('/')
        self.interval = interval
        self.database = database
        self.crawler = crawler
        self.on_change = on_change
        self.results = {}
        self.pages = []
        self._running = False
        self._task = None

    async def discover_pages(self):
        if self.crawler:
            self.pages = await self.crawler.crawl()
        return self.pages

    async def start(self):
        if self._task and not self._task.done():
            return
        self._task = True

    async def stop(self):
        self._running = False
