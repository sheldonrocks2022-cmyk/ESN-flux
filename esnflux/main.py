import asyncio
import uvicorn

from .settings import settings
from .database import Database
from .monitor import SMPMonitor
from .website import WebsiteMonitor
from .website_crawler import WebsiteCrawler
from .website_commands import WebsiteGroup
from .bot import ESNFluxBot
from .api import build_api


async def run():
    database = Database(settings.database_path)
    await database.connect()

    bot = ESNFluxBot(None, database, settings)
    monitor = SMPMonitor(settings.smp_host, settings.smp_port, settings.monitor_interval, database)
    crawler = WebsiteCrawler(settings.website_url, database)
    crawler.scan_interval = settings.website_scan_interval
    website_monitor = WebsiteMonitor(
        settings.website_url,
        settings.website_monitor_interval,
        database,
        crawler=crawler,
    )

    bot.monitor = monitor
    bot.website_monitor = website_monitor
    bot.tree.add_command(WebsiteGroup(bot))
    monitor.on_change = bot.state_changed
    website_monitor.on_change = bot.website_changed

    api = build_api(monitor, database, settings, website_monitor)
    server = uvicorn.Server(uvicorn.Config(api, host=settings.api_host, port=settings.api_port, log_level='info'))

    await bot.initialize_state()
    await monitor.start()
    await website_monitor.start()
    api_task = asyncio.create_task(server.serve(), name='esnflux-api')

    try:
        await bot.start(settings.discord_token)
    finally:
        await monitor.stop()
        await website_monitor.stop()
        server.should_exit = True
        await api_task
        await database.close()


def main():
    asyncio.run(run())


if __name__ == '__main__':
    main()
