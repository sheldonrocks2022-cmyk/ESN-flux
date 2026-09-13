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
        CREATE TABLE IF NOT EXISTS smp_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            event_type TEXT NOT NULL,
            player_name TEXT NOT NULL,
            message TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS website_samples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            checked_at TEXT NOT NULL,
            path TEXT NOT NULL,
            url TEXT NOT NULL,
            available INTEGER NOT NULL,
            status_code INTEGER,
            response_ms REAL,
            error TEXT
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_samples_checked ON server_samples(checked_at);
        CREATE INDEX IF NOT EXISTS idx_sessions_player ON player_sessions(player_name);
        CREATE INDEX IF NOT EXISTS idx_incidents_kind_resolved ON incidents(kind, resolved_at);
        CREATE INDEX IF NOT EXISTS idx_events_type_created ON smp_events(event_type, created_at);
        CREATE INDEX IF NOT EXISTS idx_events_player ON smp_events(player_name);
        CREATE INDEX IF NOT EXISTS idx_website_path_checked ON website_samples(path, checked_at);
        CREATE INDEX IF NOT EXISTS idx_website_checked ON website_samples(checked_at);
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

    async def get_player_sessions(self, name: str):
        cursor = await self._db.execute(
            'SELECT * FROM player_sessions WHERE lower(player_name)=lower(?) ORDER BY id DESC', (name,)
        )
        return [dict(row) for row in await cursor.fetchall()]

    async def get_player_leaderboard(self, limit=10):
        cursor = await self._db.execute('''
            SELECT player_name,
                   COALESCE(SUM(CASE WHEN duration_seconds IS NOT NULL THEN duration_seconds ELSE 0 END), 0) AS total_seconds,
                   COUNT(*) AS sessions
            FROM player_sessions
            GROUP BY player_name
            ORDER BY total_seconds DESC, sessions DESC, player_name ASC
            LIMIT ?
        ''', (limit,))
        return [dict(row) for row in await cursor.fetchall()]

    async def get_recent_player_sessions(self, limit=10):
        cursor = await self._db.execute(
            'SELECT * FROM player_sessions ORDER BY id DESC LIMIT ?', (limit,)
        )
        return [dict(row) for row in await cursor.fetchall()]

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

    async def get_recent_incidents(self, limit=10):
        cursor = await self._db.execute(
            'SELECT * FROM incidents ORDER BY id DESC LIMIT ?', (limit,)
        )
        return [dict(row) for row in await cursor.fetchall()]

    async def record_event(self, event_type: str, player_name: str, message: str):
        now = datetime.now(timezone.utc).isoformat()
        await self._db.execute(
            'INSERT INTO smp_events(created_at,event_type,player_name,message) VALUES(?,?,?,?)',
            (now, event_type, player_name, message)
        )
        await self._db.commit()

    async def get_recent_events(self, event_type=None, limit=10):
        if event_type:
            cursor = await self._db.execute(
                'SELECT * FROM smp_events WHERE event_type=? ORDER BY id DESC LIMIT ?',
                (event_type, limit)
            )
        else:
            cursor = await self._db.execute(
                'SELECT * FROM smp_events ORDER BY id DESC LIMIT ?', (limit,)
            )
        return [dict(row) for row in await cursor.fetchall()]

    async def get_recent_samples(self, limit=100):
        cursor = await self._db.execute(
            'SELECT * FROM server_samples ORDER BY id DESC LIMIT ?', (limit,)
        )
        return [dict(row) for row in await cursor.fetchall()]

    async def get_stats(self, limit=500):
        cursor = await self._db.execute(
            'SELECT online, players, latency_ms, checked_at FROM server_samples ORDER BY id DESC LIMIT ?',
            (limit,)
        )
        samples = [dict(row) for row in await cursor.fetchall()]
        if not samples:
            return {
                'sample_count': 0,
                'uptime_pct': 0.0,
                'average_players': 0.0,
                'peak_players': 0,
                'average_latency_ms': None,
                'latest_sample_at': None,
            }
        online_samples = sum(1 for sample in samples if sample['online'])
        player_values = [sample['players'] for sample in samples]
        latencies = [sample['latency_ms'] for sample in samples if sample['latency_ms'] is not None]
        return {
            'sample_count': len(samples),
            'uptime_pct': round((online_samples / len(samples)) * 100, 2),
            'average_players': round(sum(player_values) / len(player_values), 2),
            'peak_players': max(player_values),
            'average_latency_ms': round(sum(latencies) / len(latencies), 2) if latencies else None,
            'latest_sample_at': samples[0]['checked_at'],
        }

    async def record_website_sample(self, result):
        now = datetime.fromtimestamp(result.checked_at, timezone.utc).isoformat()
        await self._db.execute(
            'INSERT INTO website_samples(checked_at,path,url,available,status_code,response_ms,error) VALUES(?,?,?,?,?,?,?)',
            (now, result.path, result.url, int(result.available), result.status_code, result.response_ms, result.error)
        )
        await self._db.commit()

    async def get_recent_website_samples(self, limit=50):
        cursor = await self._db.execute(
            'SELECT * FROM website_samples ORDER BY id DESC LIMIT ?', (limit,)
        )
        return [dict(row) for row in await cursor.fetchall()]

    async def get_website_stats(self, limit=5000):
        cursor = await self._db.execute('''
            SELECT path,
                   COUNT(*) AS samples,
                   SUM(available) AS available_samples,
                   AVG(response_ms) AS average_response_ms,
                   MAX(response_ms) AS max_response_ms,
                   MAX(checked_at) AS latest_checked_at
            FROM website_samples
            GROUP BY path
            ORDER BY path ASC
            LIMIT ?
        ''', (limit,))
        rows = [dict(row) for row in await cursor.fetchall()]
        for row in rows:
            row['uptime_pct'] = round((row['available_samples'] / row['samples']) * 100, 2) if row['samples'] else 0.0
            if row['average_response_ms'] is not None:
                row['average_response_ms'] = round(row['average_response_ms'], 2)
            if row['max_response_ms'] is not None:
                row['max_response_ms'] = round(row['max_response_ms'], 2)
        return rows

    async def get_website_overall(self):
        cursor = await self._db.execute('''
            SELECT COUNT(*) AS samples,
                   SUM(available) AS available_samples,
                   AVG(response_ms) AS average_response_ms,
                   MAX(response_ms) AS max_response_ms,
                   MAX(checked_at) AS latest_checked_at
            FROM website_samples
        ''')
        row = dict(await cursor.fetchone())
        samples = row['samples'] or 0
        row['uptime_pct'] = round(((row['available_samples'] or 0) / samples) * 100, 2) if samples else 0.0
        if row['average_response_ms'] is not None:
            row['average_response_ms'] = round(row['average_response_ms'], 2)
        if row['max_response_ms'] is not None:
            row['max_response_ms'] = round(row['max_response_ms'], 2)
        return row

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
