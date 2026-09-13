from pathlib import Path
from datetime import datetime, timezone
import aiosqlite

class Database:
    def __init__(self, path: str):
        self.path = path
        self._db = None

    async def connect(self):
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self.path)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript('''
        CREATE TABLE IF NOT EXISTS server_samples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            checked_at TEXT NOT NULL,
            online INTEGER NOT NULL,
            players INTEGER NOT NULL DEFAULT 0,
            latency_ms REAL,
            player_names TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS player_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_name TEXT NOT NULL,
            joined_at TEXT NOT NULL,
            left_at TEXT,
            duration_seconds INTEGER
        );
        CREATE TABLE IF NOT EXISTS incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            resolved_at TEXT,
            kind TEXT NOT NULL,
            message TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_samples_checked ON server_samples(checked_at);
        CREATE INDEX IF NOT EXISTS idx_sessions_player ON player_sessions(player_name);
        CREATE INDEX IF NOT EXISTS idx_incidents_kind_resolved ON incidents(kind, resolved_at);
        ''')
        await self._db.commit()

    async def close(self):
        if self._db:
            await self._db.close()
            self._db = None

    async def sample(self, online: bool, players: int, latency_ms, names: list[str]):
        now = datetime.now(timezone.utc).isoformat()
        await self._db.execute(
            'INSERT INTO server_samples(checked_at,online,players,latency_ms,player_names) VALUES(?,?,?,?,?)',
            (now, int(online), players, latency_ms, '\n'.join(sorted(names)))
        )
        await self._db.commit()

    async def open_session(self, name: str):
        cursor = await self._db.execute(
            'SELECT id FROM player_sessions WHERE player_name=? AND left_at IS NULL LIMIT 1', (name,)
        )
        if await cursor.fetchone():
            return
        now = datetime.now(timezone.utc).isoformat()
        await self._db.execute('INSERT INTO player_sessions(player_name,joined_at) VALUES(?,?)', (name, now))
        await self._db.commit()

    async def close_session(self, name: str):
        now = datetime.now(timezone.utc)
        cursor = await self._db.execute(
            'SELECT id, joined_at FROM player_sessions WHERE player_name=? AND left_at IS NULL ORDER BY id DESC LIMIT 1',
            (name,)
        )
        row = await cursor.fetchone()
        if not row:
            return
        joined = datetime.fromisoformat(row['joined_at'])
        duration = max(0, int((now - joined).total_seconds()))
        await self._db.execute(
            'UPDATE player_sessions SET left_at=?, duration_seconds=? WHERE id=?',
            (now.isoformat(), duration, row['id'])
        )
        await self._db.commit()

    async def get_active_sessions(self):
        cursor = await self._db.execute(
            'SELECT player_name FROM player_sessions WHERE left_at IS NULL ORDER BY player_name'
        )
        return [row['player_name'] for row in await cursor.fetchall()]

    async def incident(self, kind: str, message: str):
        now = datetime.now(timezone.utc).isoformat()
        cursor = await self._db.execute(
            'INSERT INTO incidents(started_at,kind,message) VALUES(?,?,?)', (now, kind, message)
        )
        await self._db.commit()
        return cursor.lastrowid

    async def incident_once(self, kind: str, message: str):
        cursor = await self._db.execute(
            'SELECT id FROM incidents WHERE kind=? AND resolved_at IS NULL ORDER BY id DESC LIMIT 1', (kind,)
        )
        if await cursor.fetchone():
            return None
        return await self.incident(kind, message)

    async def resolve_latest(self, kind: str):
        now = datetime.now(timezone.utc).isoformat()
        await self._db.execute(
            'UPDATE incidents SET resolved_at=? WHERE id=(SELECT id FROM incidents WHERE kind=? AND resolved_at IS NULL ORDER BY id DESC LIMIT 1)',
            (now, kind)
        )
        await self._db.commit()

    async def get_recent_samples(self, limit=100):
        cursor = await self._db.execute(
            'SELECT * FROM server_samples ORDER BY id DESC LIMIT ?', (limit,)
        )
        return [dict(row) for row in await cursor.fetchall()]

    async def set_value(self, key: str, value: str):
        await self._db.execute(
            'INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
            (key, value)
        )
        await self._db.commit()

    async def get_value(self, key: str, default=None):
        cursor = await self._db.execute('SELECT value FROM settings WHERE key=?', (key,))
        row = await cursor.fetchone()
        return row['value'] if row else default
