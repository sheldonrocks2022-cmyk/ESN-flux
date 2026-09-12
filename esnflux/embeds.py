import discord
from datetime import datetime, timezone

BLACK = 0x050805
GREEN = 0x35FF69
DARK_GREEN = 0x0D3B1B


def _base(title: str, description: str, *, icon: str = "🟢") -> discord.Embed:
    embed = discord.Embed(
        title=f"{icon}  ESN SMP  //  {title.upper()}",
        description=description,
        colour=GREEN,
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_footer(text="ESNFlux • SMP Operations")
    embed.set_author(name="ESNFLUX  |  SMP MONITOR")
    return embed


def status_embed(online: bool, players: int, latency_ms, error=None):
    if online:
        embed = _base("Server Online", "The ESN SMP connection is healthy.", icon="🟢")
        embed.add_field(name="STATUS", value="`ONLINE`", inline=True)
        embed.add_field(name="PLAYERS", value=f"`{players}`", inline=True)
        embed.add_field(name="LATENCY", value=f"`{latency_ms:.0f} ms`" if latency_ms else "`—`", inline=True)
        return embed
    embed = _base("Server Offline", "ESNFlux cannot currently reach the ESN SMP.", icon="🔴")
    embed.colour = discord.Colour(0x35FF69)
    embed.add_field(name="STATUS", value="`OFFLINE`", inline=True)
    if error:
        embed.add_field(name="DETAIL", value=f"`{error[:900]}`", inline=False)
    return embed


def player_embed(name: str, joined: bool, players: int):
    action = "PLAYER JOINED" if joined else "PLAYER LEFT"
    icon = "🟢" if joined else "🟠"
    embed = _base(action, f"`{name}` has {'joined' if joined else 'left'} the ESN SMP.", icon=icon)
    embed.add_field(name="PLAYER", value=f"`{name}`", inline=True)
    embed.add_field(name="ONLINE", value=f"`{players}`", inline=True)
    return embed


def peak_embed(players: int):
    embed = _base("New Player Peak", f"The SMP reached a new peak of **{players} players**.", icon="📈")
    embed.add_field(name="NEW PEAK", value=f"`{players}` players", inline=True)
    return embed


def incident_embed(kind: str, message: str, resolved=False):
    icon = "🟢" if resolved else "🚨"
    title = f"{kind} Resolved" if resolved else kind
    embed = _base(title, message, icon=icon)
    embed.add_field(name="INCIDENT", value=f"`{kind}`", inline=True)
    embed.add_field(name="STATE", value="`RESOLVED`" if resolved else "`ACTIVE`", inline=True)
    return embed
