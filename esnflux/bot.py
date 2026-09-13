import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timezone
from .embeds import status_embed, player_embed, peak_embed


class ESNFluxBot(commands.Bot):
    def __init__(self, monitor, database, settings):
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)
        self.monitor = monitor
        self.database = database
        self.settings = settings
        self.previous_players: set[str] = set()
        self.previous_online = False
        self.peak = 0
        self._state_initialized = False

    async def setup_hook(self):
        self.tree.add_command(SMPGroup(self))
        if self.settings.discord_guild_id:
            guild = discord.Object(id=self.settings.discord_guild_id)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()

    async def initialize_state(self):
        if self._state_initialized:
            return
        self.peak = int(await self.database.get_value("smp_peak", "0"))
        self.previous_players = set(await self.database.get_active_sessions())
        self.previous_online = self.monitor.state.online
        self._state_initialized = True

    async def on_ready(self):
        await self.initialize_state()
        await self.change_presence(activity=discord.Game(name="ESN SMP monitoring"))

    async def send_log(self, embed):
        channel_id = self.settings.smp_log_channel_id
        if not channel_id:
            return
        channel = self.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self.fetch_channel(channel_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                return
        if hasattr(channel, "send"):
            try:
                await channel.send(embed=embed)
            except (discord.Forbidden, discord.HTTPException):
                pass

    async def state_changed(self, old, new):
        if old.online != new.online:
            await self.send_log(status_embed(new.online, new.players, new.latency_ms, new.error))
            if new.online:
                await self.database.resolve_latest("SMP_OFFLINE")
            else:
                await self.database.incident_once("SMP_OFFLINE", new.error or "ESN SMP became unreachable")

        if not new.online and self.previous_players:
            for name in sorted(self.previous_players):
                await self.database.close_session(name)
            self.previous_players = set()

        if new.online and new.player_names_available:
            current = set(new.player_names)
            for name in sorted(current - self.previous_players):
                await self.database.open_session(name)
                await self.send_log(player_embed(name, True, new.players))
            for name in sorted(self.previous_players - current):
                await self.database.close_session(name)
                await self.send_log(player_embed(name, False, new.players))
            self.previous_players = current

        if new.online and new.players > self.peak:
            self.peak = new.players
            await self.database.set_value("smp_peak", str(self.peak))
            await self.send_log(peak_embed(new.players))

        self.previous_online = new.online


class SMPGroup(app_commands.Group):
    def __init__(self, bot):
        super().__init__(name="smp", description="ESN SMP operations")
        self.bot = bot

    def _embed(self, title: str, description: str, colour: int = 0x35FF69):
        embed = discord.Embed(
            title=f"🟢 ESN SMP // {title.upper()}",
            description=description,
            colour=colour,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_footer(text="ESNFlux • SMP Operations")
        return embed

    @app_commands.command(name="status", description="Show current ESN SMP status")
    async def status(self, interaction: discord.Interaction):
        state = self.bot.monitor.state
        await interaction.response.send_message(
            embed=status_embed(state.online, state.players, state.latency_ms, state.error),
            ephemeral=True,
        )

    @app_commands.command(name="players", description="Show the currently detected players")
    async def players(self, interaction: discord.Interaction):
        state = self.bot.monitor.state
        if not state.player_names_available:
            text = "Player names are currently unavailable from the Bedrock query."
        else:
            text = "\n".join(f"• `{name}`" for name in state.player_names) if state.player_names else "No players are currently detected."
        await interaction.response.send_message(embed=self._embed("Players", text), ephemeral=True)

    @app_commands.command(name="info", description="Show ESN SMP connection and monitoring information")
    async def info(self, interaction: discord.Interaction):
        state = self.bot.monitor.state
        embed = self._embed("Server Info", "Official ESN SMP monitoring information.")
        embed.add_field(name="ADDRESS", value=f"`{self.bot.settings.smp_host}`", inline=False)
        embed.add_field(name="PORT", value=f"`{self.bot.settings.smp_port}`", inline=True)
        embed.add_field(name="MONITOR INTERVAL", value=f"`{self.bot.settings.monitor_interval}s`", inline=True)
        embed.add_field(name="CURRENT STATUS", value="`ONLINE`" if state.online else "`OFFLINE`", inline=True)
        embed.add_field(name="CURRENT PLAYERS", value=f"`{state.players}`", inline=True)
        embed.add_field(name="PLAYER NAMES", value="`AVAILABLE`" if state.player_names_available else "`UNAVAILABLE`", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="stats", description="Show long-term ESN SMP monitoring statistics")
    async def stats(self, interaction: discord.Interaction):
        stats = await self.bot.database.get_stats()
        embed = self._embed("Statistics", "ESN Flux monitoring statistics from stored SMP samples.")
        embed.add_field(name="SAMPLES", value=f"`{stats['sample_count']}`", inline=True)
        embed.add_field(name="UPTIME", value=f"`{stats['uptime_pct']}%`", inline=True)
        embed.add_field(name="AVERAGE PLAYERS", value=f"`{stats['average_players']}`", inline=True)
        embed.add_field(name="PEAK PLAYERS", value=f"`{stats['peak_players']}`", inline=True)
        embed.add_field(name="AVERAGE LATENCY", value=f"`{stats['average_latency_ms']} ms`" if stats['average_latency_ms'] is not None else "`—`", inline=True)
        if stats['latest_sample_at']:
            embed.add_field(name="LATEST SAMPLE", value=f"`{stats['latest_sample_at']}`", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="player", description="Show stored session history for a player")
    @app_commands.describe(name="Minecraft player name")
    async def player(self, interaction: discord.Interaction, name: str):
        rows = await self.bot.database.get_player_sessions(name)
        if not rows:
            await interaction.response.send_message(embed=self._embed("Player", f"No stored session history was found for `{name}`."), ephemeral=True)
            return
        total_seconds = sum(int(row.get("duration_seconds") or 0) for row in rows)
        active = any(row.get("left_at") is None for row in rows)
        embed = self._embed("Player History", f"Stored ESN SMP history for `{name}`.")
        embed.add_field(name="SESSIONS", value=f"`{len(rows)}`", inline=True)
        embed.add_field(name="TOTAL TIME", value=f"`{total_seconds // 3600}h {(total_seconds % 3600) // 60}m`", inline=True)
        embed.add_field(name="CURRENTLY ONLINE", value="`YES`" if active else "`NO`", inline=True)
        recent = []
        for row in rows[:5]:
            joined = row.get("joined_at", "unknown")
            left = row.get("left_at") or "ACTIVE"
            recent.append(f"• `{joined}` → `{left}`")
        embed.add_field(name="RECENT SESSIONS", value="\n".join(recent), inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="leaderboard", description="Show the most active tracked SMP players")
    async def leaderboard(self, interaction: discord.Interaction):
        rows = await self.bot.database.get_player_leaderboard(10)
        if not rows:
            text = "No player session history has been recorded yet."
        else:
            text = "\n".join(
                f"**{index}.** `{row['player_name']}` — `{int(row['total_seconds'] or 0) // 3600}h {(int(row['total_seconds'] or 0) % 3600) // 60}m`"
                for index, row in enumerate(rows, 1)
            )
        await interaction.response.send_message(embed=self._embed("Leaderboard", text), ephemeral=True)

    @app_commands.command(name="history", description="Show recent server monitoring history")
    @app_commands.describe(limit="Number of recent samples to show, from 5 to 20")
    async def history(self, interaction: discord.Interaction, limit: app_commands.Range[int, 5, 20] = 10):
        rows = await self.bot.database.get_recent_samples(limit)
        if not rows:
            text = "No monitoring history has been recorded yet."
        else:
            text = "\n".join(
                f"• `{row['checked_at']}` — {'ONLINE' if row['online'] else 'OFFLINE'} — `{row['players']}` players"
                for row in rows
            )
        await interaction.response.send_message(embed=self._embed("History", text), ephemeral=True)

    @app_commands.command(name="activity", description="Show recent tracked player activity")
    async def activity(self, interaction: discord.Interaction):
        rows = await self.bot.database.get_recent_player_sessions(10)
        if not rows:
            text = "No player activity has been recorded yet."
        else:
            text = "\n".join(
                f"• `{row['player_name']}` — joined `{row['joined_at']}` — {'ACTIVE' if row['left_at'] is None else 'left ' + row['left_at']}"
                for row in rows
            )
        await interaction.response.send_message(embed=self._embed("Activity", text), ephemeral=True)

    @app_commands.command(name="logs", description="Show recent SMP incidents and monitoring events")
    async def logs(self, interaction: discord.Interaction):
        incidents = await self.bot.database.get_recent_incidents(10)
        if not incidents:
            text = "No SMP incidents have been recorded."
        else:
            text = "\n".join(
                f"• `{row['started_at']}` — **{row['kind']}** — {row['message'][:100]}{'...' if len(row['message']) > 100 else ''}"
                for row in incidents
            )
        await interaction.response.send_message(embed=self._embed("Logs", text), ephemeral=True)

    @app_commands.command(name="deaths", description="Show tracked SMP death events")
    async def deaths(self, interaction: discord.Interaction):
        events = await self.bot.database.get_recent_events("death", 10)
        if not events:
            text = "No death events have been recorded yet. Flux needs an event source/API that exposes Minecraft death events to track these automatically."
        else:
            text = "\n".join(f"• `{event['created_at']}` — `{event['player_name']}` — {event['message']}" for event in events)
        await interaction.response.send_message(embed=self._embed("Deaths", text), ephemeral=True)

    @app_commands.command(name="levels", description="Show tracked SMP level-up events")
    async def levels(self, interaction: discord.Interaction):
        events = await self.bot.database.get_recent_events("level_up", 10)
        if not events:
            text = "No level-up events have been recorded yet. Flux needs an event source/API that exposes Minecraft level events to track these automatically."
        else:
            text = "\n".join(f"• `{event['created_at']}` — `{event['player_name']}` — {event['message']}" for event in events)
        await interaction.response.send_message(embed=self._embed("Levels", text), ephemeral=True)
