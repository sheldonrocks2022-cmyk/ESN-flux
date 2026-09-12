import discord
from esnflux.embeds import status_embed, player_embed, peak_embed

def test_online_embed():
    embed = status_embed(True, 12, 42.5)
    assert "SERVER ONLINE" in embed.title
    assert embed.colour.value == 0x35FF69
    assert any(f.name == "PLAYERS" and "12" in f.value for f in embed.fields)

def test_offline_embed():
    embed = status_embed(False, 0, None, "Timeout")
    assert "SERVER OFFLINE" in embed.title
    assert "Timeout" in embed.fields[0].value

def test_player_embed():
    embed = player_embed("TestPlayer", True, 7)
    assert "PLAYER JOINED" in embed.title
    assert "TestPlayer" in embed.description

def test_peak_embed():
    embed = peak_embed(50)
    assert "50" in embed.description
