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
        overall = (
            await self.bot.database.get_website_overall()
        )

        rows = (
            await self.bot.database.get_website_stats()
        )

        embed = self._embed(
            "Statistics",
            "Long-term telemetry collected by ESN Flux for the ESN website.",
        )

        embed.add_field(
            name="UPTIME",
            value=f"`{overall['uptime_pct']}%`",
            inline=True,
        )

        embed.add_field(
            name="SAMPLES",
            value=f"`{overall['samples']}`",
            inline=True,
        )

        if overall["average_response_ms"] is not None:
            avg_response = (
                f"`{overall['average_response_ms']} ms`"
            )
        else:
            avg_response = "`—`"

        embed.add_field(
            name="AVG RESPONSE",
            value=avg_response,
            inline=True,
        )

        if overall["max_response_ms"] is not None:
            max_response = (
                f"`{overall['max_response_ms']} ms`"
            )
        else:
            max_response = "`—`"

        embed.add_field(
            name="MAX RESPONSE",
            value=max_response,
            inline=True,
        )

        embed.add_field(
            name="ENDPOINTS",
            value=f"`{len(rows)}`",
            inline=True,
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
        )

    @app_commands.command(
        name="endpoints",
        description="Show every monitored ESN website endpoint",
    )
    async def endpoints(
        self,
        interaction: discord.Interaction,
    ):
        rows = (
            await self.bot.database.get_website_stats()
        )

        current = (
            self.bot.website_monitor.results
        )

        if not rows and not current:
            text = (
                "No website telemetry has been recorded yet."
            )
        else:
            paths = sorted(
                set(current)
                | {
                    row["path"]
                    for row in rows
                }
            )

            lines = []

            for path in paths:
                result = current.get(path)

                if result and result.available:
                    state = "🟢 ONLINE"
                elif result:
                    state = "🔴 DOWN"
                else:
                    state = "⚪ UNKNOWN"

                lines.append(
                    f"{state} — `{path}`"
                )

            text = "\n".join(lines)

        await interaction.response.send_message(
            embed=self._embed(
                "Endpoints",
                text,
            ),
            ephemeral=True,
        )

    @app_commands.command(
        name="history",
        description="Show recent website monitoring checks",
    )
    @app_commands.describe(
        limit="Number of checks to show, from 5 to 25",
    )
    async def history(
        self,
        interaction: discord.Interaction,
        limit: app_commands.Range[int, 5, 25] = 10,
    ):
        rows = (
            await self.bot.database
            .get_recent_website_samples(limit)
        )

        if not rows:
            text = (
                "No website history has been recorded yet."
            )
        else:
            lines = []

            for row in rows:
                if row["response_ms"] is not None:
                    response_time = (
                        f"{round(row['response_ms'])} ms"
                    )
                else:
                    response_time = "— ms"

                state = (
                    "ONLINE"
                    if row["available"]
                    else "DOWN"
                )

                lines.append(
                    f"• `{row['checked_at']}` — "
                    f"`{row['path']}` — "
                    f"{state} — "
                    f"`{response_time}`"
                )

            text = "\n".join(lines)

        await interaction.response.send_message(
            embed=self._embed(
                "History",
                text,
            ),
            ephemeral=True,
        )

    @app_commands.command(
        name="check",
        description="Immediately check a monitored website path",
    )
    @app_commands.describe(
        path="Website path such as / or /smp",
    )
    async def check(
        self,
        interaction: discord.Interaction,
        path: str = "/",
    ):
        path = "/" + path.lstrip("/")

        if path not in DEFAULT_PATHS:
            await interaction.response.send_message(
                embed=self._embed(
                    "Check",
                    f"`{path}` is not one of the monitored endpoints.",
                ),
                ephemeral=True,
            )
            return

        try:
            async with httpx.AsyncClient(
                timeout=15,
                follow_redirects=True,
                headers={
                    "User-Agent": "ESNFlux/WebsiteMonitor"
                },
            ) as client:
                result = (
                    await self.bot.website_monitor
                    .probe_path(client, path)
                )

        except Exception as exc:
            await interaction.response.send_message(
                embed=self._embed(
                    "Check",
                    f"Unable to check `{path}`.\n\n"
                    f"Error: `{str(exc)[:500]}`",
                ),
                ephemeral=True,
            )
            return

        state = (
            "🟢 ONLINE"
            if result.available
            else "🔴 DOWN"
        )

        http_status = (
            result.status_code
            if result.status_code is not None
            else "—"
        )

        response_time = (
            round(result.response_ms)
            if result.response_ms is not None
            else "—"
        )

        detail = (
            f"**{state}**\n"
            f"HTTP: `{http_status}`\n"
            f"Response: `{response_time} ms`"
        )

        if result.error:
            detail += (
                f"\nError: `{result.error[:500]}`"
            )

        await interaction.response.send_message(
            embed=self._embed(
                "Check",
                f"`{path}`\n\n{detail}",
            ),
            ephemeral=True,
        )
```
