import os
from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    val = os.getenv(name)
    if not val:
        raise RuntimeError(f"Missing required env variable: {name}")
    return val


TELEGRAM_BOT_TOKEN = _require("TELEGRAM_BOT_TOKEN")
ZOOM_LINK = _require("ZOOM_LINK")
LANDING_URL = _require("LANDING_URL")
CALL_LINK = _require("CALL_LINK")

_admin_raw = _require("ADMIN_IDS")
ADMIN_IDS = {int(x.strip()) for x in _admin_raw.split(",") if x.strip()}

DB_PATH = os.getenv("DB_PATH", "sas_bot.db")
TIMEZONE = "Europe/Moscow"
