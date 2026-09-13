import asyncio
import uvicorn

from .settings import settings
from .database import Database
from .monitor import SMPMonitor
from .website import WebsiteMonitor
from .website_crawler import WebsiteCrawler
from .website_commands import WebsiteGroup
from .website_logger import WebsiteLogger
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
    bot.website_logger = WebsiteLogger(bot, settings.website_log_channel_id)
    bot.tree.add_command(WebsiteGroup(bot))
    monitor.on_change = bot.state_changed

    async def website_changed(old, new):
        await bot.website_changed(old, new)
        logger = getattr(bot, "website_logger", None)
        if not logger:
            return
        if old is None and new:
            await logger.page_discovered(new.url)
        elif old and new and old.available and not new.available:
            await logger.website_down(new.url, new.error or "Unknown error")
        elif old and new and not old.available and new.available:
            await logger.website_restored(new.url)

    website_monitor.on_change = website_changed

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
