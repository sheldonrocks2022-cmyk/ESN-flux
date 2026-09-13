from fastapi import FastAPI, Header, HTTPException
from .settings import settings as default_settings


def build_api(monitor, database, config=None):
    app = FastAPI(title="ESNFlux SMP API", version="1.0")
    config = config or default_settings

    def authorize(key):
        if config.api_key and key != config.api_key:
            raise HTTPException(status_code=401, detail="Unauthorized")

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "service": "ESNFlux", "smp_online": monitor.state.online}

    @app.get("/api/smp/status")
    async def status():
        state = monitor.state
        return {
            "online": state.online,
            "players": state.players,
            "player_names": state.player_names,
            "latency_ms": state.latency_ms,
            "checked_at": state.checked_at,
            "error": state.error,
        }

    @app.get("/api/smp/players")
    async def players():
        return {"online": monitor.state.online, "count": monitor.state.players, "players": monitor.state.player_names}

    @app.get("/api/smp/history")
    async def history(limit: int = 100, x_api_key: str | None = Header(default=None)):
        authorize(x_api_key)
        limit = min(max(limit, 1), 500)
        return {"samples": await database.get_recent_samples(limit)}

    return app
