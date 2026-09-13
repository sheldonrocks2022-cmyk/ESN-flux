import pytest

from esnflux.database import Database


@pytest.mark.asyncio
async def test_sessions_are_not_duplicated_and_duration_is_recorded(tmp_path):
    db = Database(str(tmp_path / "flux.db"))
    await db.connect()
    await db.open_session("Steve")
    await db.open_session("Steve")
    await db.close_session("Steve")

    cursor = await db._db.execute("SELECT COUNT(*) AS count FROM player_sessions")
    row = await cursor.fetchone()
    assert row["count"] == 1

    cursor = await db._db.execute("SELECT left_at, duration_seconds FROM player_sessions WHERE player_name='Steve'")
    row = await cursor.fetchone()
    assert row["left_at"] is not None
    assert row["duration_seconds"] >= 0
    await db.close()


@pytest.mark.asyncio
async def test_incident_once_does_not_duplicate_active_incidents(tmp_path):
    db = Database(str(tmp_path / "flux.db"))
    await db.connect()
    first = await db.incident_once("SMP_OFFLINE", "timeout")
    second = await db.incident_once("SMP_OFFLINE", "timeout again")
    assert first is not None
    assert second is None

    await db.resolve_latest("SMP_OFFLINE")
    third = await db.incident_once("SMP_OFFLINE", "another outage")
    assert third is not None
    await db.close()


@pytest.mark.asyncio
async def test_settings_persist_values(tmp_path):
    db = Database(str(tmp_path / "flux.db"))
    await db.connect()
    assert await db.get_value("smp_peak", "0") == "0"
    await db.set_value("smp_peak", "42")
    assert await db.get_value("smp_peak") == "42"
    await db.close()
