from datetime import datetime, timezone


class WebsiteLogger:
    """Handles formatting website monitoring events for Discord output."""

    def __init__(self, bot, channel_id: int):
        self.bot = bot
        self.channel_id = channel_id

    async def send(self, title: str, message: str, success: bool = True):
        if not self.channel_id:
            return

        channel = self.bot.get_channel(self.channel_id)
        if channel is None:
            return

        color = 0x00FF00 if success else 0xFF0000
        embed = {
            "title": title,
            "description": message,
            "color": color,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "footer": {"text": "ESN Flux Website Monitor"},
        }

        await channel.send(embed=embed)

    async def page_discovered(self, url: str):
        await self.send("🔎 New Website Page Discovered", url)

    async def website_down(self, url: str, error: str):
        await self.send("🔴 Website Page Offline", f"{url}\n{error}", False)

    async def website_restored(self, url: str):
        await self.send("🟢 Website Page Restored", url)
