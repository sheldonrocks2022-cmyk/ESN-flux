import asyncio
import uvicorn
from .settings import settings
from .database import Database
from .monitor import SMPMonitor
from .bot import ESNFluxBot
from .api import build_api

async def run():
    database = Database(settings.database_path)
    await database.connect()
    bot = ESNFluxBot(None, database, settings)
    monitor = SMPMonitor(settings.smp_host, settings.smp_port, settings.monitor_interval, database)
    monitor.on_change = bot.state_changed
    bot.monitor = monitor
    api = build_api(monitor, database)
    server = uvicorn.Server(uvicorn.Config(api, host=settings.api_host, port=settings.api_port, log_level="info"))
    monitor_task = asyncio.create_task(monitor.start())
    api_task = asyncio.create_task(server.serve())
    try:
        await bot.start(settings.discord_token)
    finally:
        await monitor.stop()
        server.should_exit = True
        await api_task
        await database.close()
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass

def main():
    asyncio.run(run())

if __name__ == "__main__":
    main()
