import asyncio
from urllib.parse import urljoin, urlparse
import httpx
from bs4 import BeautifulSoup


class WebsiteCrawler:
    def __init__(self, base_url, database, max_pages=200):
        self.base_url = base_url.rstrip('/')
        self.domain = urlparse(self.base_url).netloc
        self.database = database
        self.max_pages = max_pages
        self.pages = set()

    def valid_url(self, url):
        parsed = urlparse(url)
        return (
            parsed.scheme in ('http', 'https')
            and parsed.netloc == self.domain
            and not any(parsed.path.lower().endswith(x) for x in ('.png','.jpg','.jpeg','.gif','.svg','.css','.js','.zip','.mp4'))
        )

    async def crawl(self):
        queue = [self.base_url]
        seen = set()
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            while queue and len(seen) < self.max_pages:
                url = queue.pop(0)
                if url in seen:
                    continue
                seen.add(url)
                try:
                    response = await client.get(url)
                    if 'text/html' not in response.headers.get('content-type', ''):
                        continue
                    soup = BeautifulSoup(response.text, 'html.parser')
                    self.pages.add(url)
                    for link in soup.find_all('a', href=True):
                        target = urljoin(url, link['href']).split('#')[0]
                        if self.valid_url(target) and target not in seen:
                            queue.append(target)
                except Exception:
                    continue

        if hasattr(self.database, 'record_discovered_page'):
            for page in self.pages:
                await self.database.record_discovered_page(page)
        return sorted(self.pages)

    async def run(self, interval=3600):
        while True:
            await self.crawl()
            await asyncio.sleep(interval)
