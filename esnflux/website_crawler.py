import asyncio
from collections import deque
from urllib.parse import urljoin, urlparse, urldefrag
import httpx
from bs4 import BeautifulSoup


class WebsiteCrawler:
    IGNORED_EXTENSIONS = {
        '.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.ico', '.css', '.js', '.json',
        '.xml', '.pdf', '.zip', '.rar', '.7z', '.mp3', '.wav', '.ogg', '.mp4', '.webm', '.mov',
        '.avi', '.mkv', '.woff', '.woff2', '.ttf', '.eot', '.map'
    }

    def __init__(self, base_url, database, max_pages=500):
        self.base_url = self.normalize(base_url)
        self.domain = urlparse(self.base_url).netloc.lower()
        self.database = database
        self.max_pages = max_pages
        self.pages = set()

    def normalize(self, url):
        url, _ = urldefrag(url.strip())
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return url
        scheme = parsed.scheme.lower()
        host = parsed.hostname.lower() if parsed.hostname else ''
        port = parsed.port
        netloc = host
        if port and not ((scheme == 'http' and port == 80) or (scheme == 'https' and port == 443)):
            netloc = f'{host}:{port}'
        path = parsed.path or '/'
        if path != '/' and path.endswith('/'):
            path = path.rstrip('/')
        return f'{scheme}://{netloc}{path}'

    def valid_url(self, url):
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https') or parsed.netloc.lower() != self.domain:
            return False
        path = parsed.path.lower()
        return not any(path.endswith(ext) for ext in self.IGNORED_EXTENSIONS)

    async def crawl(self):
        queue = deque([self.base_url])
        seen = set()
        discovered = set()
        started = asyncio.get_running_loop().time()
        error = None
        headers = {'User-Agent': 'ESNFlux/WebsiteCrawler (+https://esnoffical.com)'}

        async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers=headers) as client:
            while queue and len(seen) < self.max_pages:
                url = queue.popleft()
                if url in seen:
                    continue
                seen.add(url)
                try:
                    response = await client.get(url)
                    if 'text/html' not in response.headers.get('content-type', '').lower():
                        continue
                    final_url = self.normalize(str(response.url))
                    if self.valid_url(final_url):
                        discovered.add(final_url)
                    soup = BeautifulSoup(response.text, 'html.parser')
                    for link in soup.find_all('a', href=True):
                        href = link.get('href', '').strip()
                        if not href or href.startswith(('mailto:', 'tel:', 'javascript:', '#')):
                            continue
                        target = self.normalize(urljoin(str(response.url), href))
                        if self.valid_url(target) and target not in seen and target not in queue:
                            queue.append(target)
                except Exception as exc:
                    if url == self.base_url:
                        error = str(exc)[:500]

        previous = set(self.pages)
        self.pages = discovered | previous
        new_pages = 0
        for page in sorted(discovered):
            if await self.database.record_discovered_page(page):
                new_pages += 1
        await self.database.mark_missing_pages(discovered)
        duration_ms = (asyncio.get_running_loop().time() - started) * 1000
        await self.database.record_website_crawl(len(discovered), new_pages, duration_ms, error)
        return sorted(discovered), new_pages

    async def run(self, interval=3600):
        while True:
            try:
                await self.crawl()
            except Exception:
                pass
            await asyncio.sleep(interval)
