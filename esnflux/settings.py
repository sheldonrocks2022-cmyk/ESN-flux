from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    discord_token: str = os.getenv("DISCORD_TOKEN", "")
    discord_guild_id: int = int(os.getenv("DISCORD_GUILD_ID", "0"))
    smp_host: str = os.getenv("SMP_HOST", "esnsmp.ggwp.cc")
    smp_port: int = int(os.getenv("SMP_PORT", "17058"))
    monitor_interval: int = max(10, int(os.getenv("MONITOR_INTERVAL", "30")))
    website_monitor_interval: int = max(30, int(os.getenv("WEBSITE_MONITOR_INTERVAL", "60")))
    database_path: str = os.getenv("DATABASE_PATH", "data/esnflux.db")
    api_host: str = os.getenv("API_HOST", "0.0.0.0")
    api_port: int = int(os.getenv("API_PORT", "8080"))
    api_key: str = os.getenv("API_KEY", "")
    website_url: str = os.getenv("WEBSITE_URL", "https://esnoffical.com").rstrip("/")
    smp_log_channel_id: int = int(os.getenv("SMP_LOG_CHANNEL_ID", "0"))
    staff_role_ids: tuple[int, ...] = tuple(
        int(x.strip()) for x in os.getenv("STAFF_ROLE_IDS", "").split(",") if x.strip()
    )

settings = Settings()
