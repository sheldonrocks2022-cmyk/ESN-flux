```python
from dataclasses import dataclass, field
import asyncio
import time
from urllib.parse import urlparse

import httpx


# Website paths that can be checked with /website check
DEFAULT_PATHS = {
    "/",
    "/smp",
}


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
    def __init__(
        self,
        base_url: str,
        interval: int,
        database,
        crawler=None,
        on_change=None,
    ):
        self.base_url = base_url.rstrip("/")
        self.interval = interval
        self.database = database
        self.crawler = crawler
        self.on_change = on_change

        self.results: dict[str, WebsiteResult] = {}
        self.pages: list[str] = []

        self._running = False
        self._task: asyncio.Task | None = None
        self._client: httpx.AsyncClient | None = None
        self._scan_lock = asyncio.Lock()

    @staticmethod
    def path_for(url: str) -> str:
        parsed = urlparse(url)
        path = parsed.path or "/"

        if not path.startswith("/"):
            path = "/" + path

        return path

    async def discover_pages(self):
        """
        Discover website pages using the crawler.

        If no crawler is configured, use the pages stored in the database.
        """
        if not self.crawler:
            rows = await self.database.get_website_pages(
                active_only=True
            )

            self.pages = [
                row["url"]
                for row in rows
                if row.get("url")
            ]

            return self.pages

        async with self._scan_lock:
            discovered, _ = await self.crawler.crawl()

            self.pages = [
                url
                for url in discovered
                if isinstance(url, str)
                and url.startswith(("http://", "https://"))
            ]

            return self.pages

    async def probe_url(
        self,
        client: httpx.AsyncClient,
        url: str,
    ) -> WebsiteResult:
        started = time.perf_counter()

        try:
            response = await client.get(url)

            elapsed = (
                time.perf_counter() - started
            ) * 1000

            available = (
                200 <= response.status_code < 400
            )

            return WebsiteResult(
                path=self.path_for(url),
                url=url,
                available=available,
                status_code=response.status_code,
                response_ms=round(elapsed, 2),
                error=(
                    None
                    if available
                    else f"HTTP {response.status_code}"
                ),
            )

        except Exception as exc:
            elapsed = (
                time.perf_counter() - started
            ) * 1000

            return WebsiteResult(
                path=self.path_for(url),
                url=url,
                available=False,
                status_code=None,
                response_ms=round(elapsed, 2),
                error=str(exc)[:500],
            )

    async def probe_path(
        self,
        client: httpx.AsyncClient,
        path: str,
    ) -> WebsiteResult:
        normalized_path = "/" + path.lstrip("/")

        url = self.base_url + normalized_path

        return await self.probe_url(
            client,
            url,
        )

    async def _scan_and_notify(self):
        old_pages = set(self.pages)

        pages = await self.discover_pages()

        if self.on_change:
            new_pages = sorted(
                set(pages) - old_pages
            )

            for url in new_pages:
                result = WebsiteResult(
                    path=self.path_for(url),
                    url=url,
                    available=True,
                )

                await self.on_change(
                    None,
                    result,
                )

    async def _check_pages(self):
        if not self.pages:
            await self.discover_pages()

        if not self._client:
            return

        for url in list(self.pages):
            result = await self.probe_url(
                self._client,
                url,
            )

            previous = self.results.get(url)

            self.results[url] = result

            try:
                await self.database.record_website_sample(
                    result
                )
            except Exception:
                # Database errors should not kill website monitoring.
                pass

            changed = (
                previous is None
                or previous.available != result.available
            )

            if not changed:
                continue

            if not result.available:
                try:
                    await self.database.incident_once(
                        "WEBSITE_DOWN",
                        f"{result.path}: "
                        f"{result.error or 'unavailable'}",
                    )
                except Exception:
                    pass

            elif previous and not previous.available:
                try:
                    await self.database.resolve_latest(
                        "WEBSITE_DOWN"
                    )
                except Exception:
                    pass

            if self.on_change:
                try:
                    await self.on_change(
                        previous,
                        result,
                    )
                except Exception:
                    pass

    async def _run(self):
        last_scan = 0.0

        try:
            self._client = httpx.AsyncClient(
                timeout=15,
                follow_redirects=True,
                headers={
                    "User-Agent": "ESNFlux/WebsiteMonitor"
                },
            )

            while self._running:
                now = time.monotonic()

                scan_interval = max(
                    300,
                    getattr(
                        self.crawler,
                        "scan_interval",
                        3600,
                    ),
                )

                if (
                    now - last_scan >= scan_interval
                    or not self.pages
                ):
                    try:
                        await self._scan_and_notify()
                    except Exception:
                        pass

                    last_scan = now

                try:
                    await self._check_pages()
                except Exception:
                    pass

                await asyncio.sleep(
                    max(10, self.interval)
                )

        finally:
            if self._client:
                try:
                    await self._client.aclose()
                except Exception:
                    pass

                self._client = None

    async def start(self):
        if self._task and not self._task.done():
            return

        self._running = True

        self._task = asyncio.create_task(
            self._run(),
            name="esnflux-website-monitor",
        )

    async def stop(self):
        self._running = False

        if self._task:
            try:
                await asyncio.wait_for(
                    self._task,
                    timeout=10,
                )
            except (
                asyncio.TimeoutError,
                asyncio.CancelledError,
            ):
                self._task.cancel()

            self._task = None
```
