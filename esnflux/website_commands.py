import discord
from discord import app_commands
from datetime import datetime, timezone
import httpx
from .website import DEFAULT_PATHS

# Website paths supported by the bot
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

    def _embed(self, title, description, colour=0x42E8F4):
        embed = discord.Embed(
            title=f"🌐 ESN WEBSITE // {title.upper()}",
            description=description,
            colour=colour,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_footer(text="ESNFlux • Website Monitoring")
        return embed

    @app_commands.command(
        name="status",
        description="Show the current ESN website endpoint status",
    )
    async def status(self, interaction: discord.Interaction):
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

        online = sum(
            1 for result in results
            if result.available
        )

        total = len(results)

        lines = [
            f"**{online}/{total}** monitored endpoints are available.",
            "",
        ]

        for result in results[:10]:
            state = (
                "🟢 ONLINE"
                if result.available
                else "🔴 DOWN"
            )

            lines.append(
                f"{state} — `{result.path}`"
            )

        await interaction.response.send_message(
            embed=self._embed(
                "Status",
                "\n".join(lines),
            ),
            ephemeral=True,
        )

    @app_commands.command(
        name="stats",
        description="Show website uptime and response statistics",
    )
    async def stats(self, interaction: discord.Interaction):
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
                    0xFF4444,
                ),
                ephemeral=True,
            )
            return

        embed = self._embed(
            "Statistics",
            "Website monitoring statistics.",
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
            name="MAX RESPONSE",
            value=(
                f"`{maximum} ms`"
                if maximum is not None
                else "`—`"
            ),
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
        description="Show every monitored website endpoint",
    )
    async def endpoints(self, interaction: discord.Interaction):
        try:
            rows = (
                await self.bot.database.get_website_stats()
            )

        except Exception as exc:
            await interaction.response.send_message(
                embed=self._embed(
                    "Endpoints",
                    "Unable to load website endpoints.\n\n"
                    f"Error: `{str(exc)[:500]}`",
                    0xFF4444,
                ),
                ephemeral=True,
            )
            return

        current = self.bot.website_monitor.results

        paths = set(current.keys())

        for row in rows:
            path = row.get("path")

            if path:
                paths.add(path)

        if not paths:
            text = (
                "No website endpoints have been recorded yet."
            )

        else:
            lines = []

            for path in sorted(paths):
                result = current.get(path)

                if result is None:
                    state = "⚪ UNKNOWN"

                elif result.available:
                    state = "🟢 ONLINE"

                else:
                    state = "🔴 DOWN"

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
        try:
            rows = (
                await self.bot.database
                .get_recent_website_samples(limit)
            )

        except Exception as exc:
            await interaction.response.send_message(
                embed=self._embed(
                    "History",
                    "Unable to load website history.\n\n"
                    f"Error: `{str(exc)[:500]}`",
                    0xFF4444,
                ),
                ephemeral=True,
            )
            return

        if not rows:
            text = (
                "No website history has been recorded yet."
            )

        else:
            lines = []

            for row in rows:
                state = (
                    "ONLINE"
                    if row.get("available")
                    else "DOWN"
                )

                response_ms = row.get(
                    "response_ms"
                )

                response_text = (
                    f"{round(response_ms)} ms"
                    if response_ms is not None
                    else "—"
                )

                lines.append(
                    f"• `{row.get('checked_at', 'unknown')}` — "
                    f"`{row.get('path', '/')}` — "
                    f"{state} — "
                    f"`{response_text}`"
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
        description="Immediately check a website path",
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
                    f"`{path}` is not a monitored endpoint.",
                    0xFFAA00,
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
                    .probe_path(
                        client,
                        path,
                    )
                )

        except Exception as exc:
            await interaction.response.send_message(
                embed=self._embed(
                    "Check",
                    f"Unable to check `{path}`.\n\n"
                    f"Error: `{str(exc)[:500]}`",
                    0xFF4444,
                ),
                ephemeral=True,
            )
            return

        state = (
            "🟢 ONLINE"
            if result.available
            else "🔴 DOWN"
        )

        status_code = (
            result.status_code
            if result.status_code is not None
            else "—"
        )

        response_ms = (
            round(result.response_ms)
            if result.response_ms is not None
            else "—"
        )

        text = (
            f"`{path}`\n\n"
            f"**{state}**\n"
            f"HTTP: `{status_code}`\n"
            f"Response: `{response_ms} ms`"
        )

        if result.error:
            text += (
                f"\nError: `{result.error[:500]}`"
            )

        await interaction.response.send_message(
            embed=self._embed(
                "Check",
                text,
            ),
            ephemeral=True,
        )
```
