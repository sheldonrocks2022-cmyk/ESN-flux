import discord
from discord import app_commands
from discord.ext import commands
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

    async def setup_hook(self):
        self.tree.add_command(SMPGroup(self))
        if self.settings.discord_guild_id:
            guild = discord.Object(id=self.settings.discord_guild_id)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()

    async def on_ready(self):
        self.peak = int(await self.database.get_value("smp_peak", "0"))
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
                for name in sorted(self.previous_players):
                    await self.database.close_session(name)
                self.previous_players = set()

        # A successful probe with no names can mean the query protocol did not
        # provide a player sample. Only treat names as authoritative when they
        # are present, or when the server explicitly reports zero players.
        names_available = bool(new.player_names) or new.players == 0
        if new.online and names_available:
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

    @app_commands.command(name="status", description="Show current ESN SMP status")
    async def status(self, interaction: discord.Interaction):
        state = self.bot.monitor.state
        await interaction.response.send_message(embed=status_embed(state.online, state.players, state.latency_ms, state.error), ephemeral=True)

    @app_commands.command(name="players", description="Show the currently detected players")
    async def players(self, interaction: discord.Interaction):
        names = self.bot.monitor.state.player_names
        text = "\n".join(f"• `{name}`" for name in names) if names else "No player names are currently available."
        embed = discord.Embed(title="🟢 ESN SMP // PLAYERS", description=text, colour=0x35FF69)
        embed.set_footer(text="ESNFlux • SMP Operations")
        await interaction.response.send_message(embed=embed, ephemeral=True)
