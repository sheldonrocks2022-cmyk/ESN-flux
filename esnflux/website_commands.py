import discord
from discord import app_commands
from datetime import datetime, timezone


class WebsiteGroup(app_commands.Group):
    def __init__(self, bot):
        super().__init__(name="website", description="ESN website monitoring operations")
        self.bot = bot

    def _embed(self, title: str, description: str, colour: int = 0x42E8F4):
        embed = discord.Embed(
            title=f"🌐 ESN WEBSITE // {title.upper()}",
            description=description,
            colour=colour,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_footer(text="ESNFlux • Website Monitoring")
        return embed

    @app_commands.command(name="status", description="Show the current ESN website endpoint status")
    async def status(self, interaction: discord.Interaction):
        monitor = self.bot.website_monitor
        results = list(monitor.results.values())
        if not results:
            await interaction.response.send_message(embed=self._embed("Status", "Website monitoring has not completed its first check yet."), ephemeral=True)
            return
        available = sum(1 for result in results if result.available)
        total = len(results)
        failed = [result for result in results if not result.available]
        description = f"**{available}/{total}** monitored endpoints are available.\n\n"
        if failed:
            description += "**Unavailable:**\n" + "\n".join(f"• `{r.path}` — {r.error or 'unavailable'}" for r in failed[:10])
        else:
            description += "All monitored ESN website endpoints are responding normally."
        await interaction.response.send_message(embed=self._embed("Status", description), ephemeral=True)

    @app_commands.command(name="stats", description="Show website uptime and response-time statistics")
    async def stats(self, interaction: discord.Interaction):
        overall = await self.bot.database.get_website_overall()
        rows = await self.bot.database.get_website_stats()
        embed = self._embed("Statistics", "Long-term telemetry collected by ESN Flux for the ESN website.")
        embed.add_field(name="UPTIME", value=f"`{overall['uptime_pct']}%`", inline=True)
        embed.add_field(name="SAMPLES", value=f"`{overall['samples']}`", inline=True)
        embed.add_field(name="AVG RESPONSE", value=f"`{overall['average_response_ms']} ms`" if overall['average_response_ms'] is not None else "`—`", inline=True)
        embed.add_field(name="MAX RESPONSE", value=f"`{overall['max_response_ms']} ms`" if overall['max_response_ms'] is not None else "`—`", inline=True)
        embed.add_field(name="ENDPOINTS", value=f"`{len(rows)}`", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="endpoints", description="Show every monitored ESN website endpoint")
    async def endpoints(self, interaction: discord.Interaction):
        rows = await self.bot.database.get_website_stats()
        current = self.bot.website_monitor.results
        if not rows and not current:
            text = "No website telemetry has been recorded yet."
        else:
            paths = sorted(set(current) | {row['path'] for row in rows})
            lines = []
            for path in paths:
                result = current.get(path)
                state = "🟢 ONLINE" if result and result.available else "🔴 DOWN" if result else "⚪ UNKNOWN"
                lines.append(f"{state} — `{path}`")
            text = "\n".join(lines)
        await interaction.response.send_message(embed=self._embed("Endpoints", text), ephemeral=True)

    @app_commands.command(name="history", description="Show recent website monitoring checks")
    @app_commands.describe(limit="Number of checks to show, from 5 to 25")
    async def history(self, interaction: discord.Interaction, limit: app_commands.Range[int, 5, 25] = 10):
        rows = await self.bot.database.get_recent_website_samples(limit)
        if not rows:
            text = "No website history has been recorded yet."
        else:
            text = "\n".join(
                f"• `{row['checked_at']}` — `{row['path']}` — {'ONLINE' if row['available'] else 'DOWN'} — `{round(row['response_ms']) if row['response_ms'] is not None else '—'} ms`"
                for row in rows
            )
        await interaction.response.send_message(embed=self._embed("History", text), ephemeral=True)

    @app_commands.command(name="check", description="Immediately check a website path")
    @app_commands.describe(path="Website path such as / or /smp")
    async def check(self, interaction: discord.Interaction, path: str = "/"):
        path = "/" + path.lstrip("/")
        if path not in self.bot.website_monitor.results and path not in self.bot.website_paths:
            await interaction.response.send_message(embed=self._embed("Check", f"`{path}` is not one of the monitored endpoints."), ephemeral=True)
            return
        result = await self.bot.website_monitor.probe_path(self.bot.website_client, path)
        state = "ONLINE" if result.available else "DOWN"
        detail = f"**{state}**\nHTTP: `{result.status_code or '—'}`\nResponse: `{round(result.response_ms or 0)} ms`"
        if result.error:
            detail += f"\nError: `{result.error[:500]}`"
        await interaction.response.send_message(embed=self._embed("Check", f"`{path}`\n\n{detail}"), ephemeral=True)
