```python
import discord
from discord import app_commands
from datetime import datetime, timezone
import httpx


# Website paths that can be checked with /website check
DEFAULT_PATHS = {
    "/",
    "/smp",
}


class WebsiteGroup(app_commands.Group):
    def __init__(self, bot):
        super().__init__(
            name="website",
            description="ESN website monitoring operations",
        )
        self.bot = bot

    def _embed(
        self,
        title: str,
        description: str,
        colour: int = 0x42E8F4,
    ):
        embed = discord.Embed(
            title=f"🌐 ESN WEBSITE // {title.upper()}",
            description=description,
            colour=colour,
            timestamp=datetime.now(timezone.utc),
        )

        embed.set_footer(
            text="ESNFlux • Website Monitoring"
        )

        return embed

    @app_commands.command(
        name="status",
        description="Show the current ESN website endpoint status",
    )
    async def status(
        self,
        interaction: discord.Interaction,
    ):
        monitor = self.bot.website_monitor
        results = list(monitor.results.values())

        if not results:
            await interaction.response.send_message(
                embed=self._embed(
                    "Status",
                    "Website monitoring has not completed its first check yet.",
                ),
                ephemeral=True,
            )
            return

        available = sum(
            1
            for result in results
            if result.available
        )

        total = len(results)

        failed = [
            result
            for result in results
            if not result.available
        ]

        description = (
            f"**{available}/{total}** monitored endpoints "
            "are available.\n\n"
        )

        if failed:
            description += "**Unavailable:**\n"

            description += "\n".join(
                f"• `{result.path}` — "
                f"{result.error or 'unavailable'}"
                for result in failed[:10]
            )
        else:
            description += (
                "All monitored ESN website endpoints "
                "are responding normally."
            )

        await interaction.response.send_message(
            embed=self._embed(
                "Status",
                description,
            ),
            ephemeral=True,
        )

    @app_commands.command(
        name="stats",
        description="Show website uptime and response-time statistics",
    )
    async def stats(
        self,
        interaction: discord.Interaction,
    ):
        try:
            overall = (
                await self.bot.database.get_website_overall()
            )

            rows = (
                await self.bot.database.get_website_stats()
            )

        except Exception as exc:
            await interaction.response.send_message(
                embed=self._embed(
                    "Statistics",
                    "Unable to load website statistics.\n\n"
                    f"Error: `{str(exc)[:500]}`",
                    colour=0xFF4444,
                ),
                ephemeral=True,
            )
            return

        embed = self._embed(
            "Statistics",
            "Long-term website monitoring telemetry.",
        )

        embed.add_field(
            name="UPTIME",
            value=f"`{overall.get('uptime_pct', 0)}%`",
            inline=True,
        )

        embed.add_field(
            name="SAMPLES",
            value=f"`{overall.get('samples', 0)}`",
            inline=True,
        )

        average = overall.get(
            "average_response_ms"
        )

        embed.add_field(
            name="AVG RESPONSE",
            value=(
                f"`{average} ms`"
                if average is not None
                else "`—`"
            ),
            inline=True,
        )

        maximum = overall.get(
            "max_response_ms"
        )

        embed.add_field(
```
