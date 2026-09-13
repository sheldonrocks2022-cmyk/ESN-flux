from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .settings import settings as default_settings


def build_api(monitor, database, config=None):
    app = FastAPI(title="ESNFlux SMP API", version="1.3")
    config = config or default_settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[config.website_url],
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["Content-Type"],
    )

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
            "player_names_available": state.player_names_available,
            "latency_ms": state.latency_ms,
            "checked_at": state.checked_at,
            "error": state.error,
        }

    @app.get("/api/smp/players")
    async def players():
        state = monitor.state
        return {
            "online": state.online,
            "count": state.players,
            "players": state.player_names,
            "names_available": state.player_names_available,
        }

    @app.get("/api/smp/stats")
    async def stats(limit: int = 500):
        limit = min(max(limit, 1), 500)
        return await database.get_stats(limit)

    @app.get("/api/smp/history")
    async def history(limit: int = 100):
        # History is public because the public dashboard consumes it directly.
        # It contains SMP telemetry only and no secrets or user data.
        limit = min(max(limit, 1), 500)
        return {"samples": await database.get_recent_samples(limit)}

    dashboard = Path(__file__).resolve().parent.parent / "web"
    if dashboard.exists():
        app.mount("/", StaticFiles(directory=dashboard, html=True), name="dashboard")

    return app
