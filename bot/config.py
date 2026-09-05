import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    # Fallback: manually parse .env if python-dotenv isn't installed
    _env_path = Path(__file__).resolve().parent.parent / ".env"
    if _env_path.exists():
        for line in _env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

BOT_TOKEN = os.environ["BOT_TOKEN"]
BOT_USERNAME = os.environ["BOT_USERNAME"]

ADMIN_IDS = {
    int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip()
}

LOG_CHANNEL_ID = os.environ.get("LOG_CHANNEL_ID")
LOG_CHANNEL_ID = int(LOG_CHANNEL_ID) if LOG_CHANNEL_ID else None

UPSTASH_REDIS_REST_URL = os.environ["UPSTASH_REDIS_REST_URL"]
UPSTASH_REDIS_REST_TOKEN = os.environ["UPSTASH_REDIS_REST_TOKEN"]

PENDING_JOB_TTL = int(os.environ.get("PENDING_JOB_TTL", "600"))

MAX_STATIC_BYTES = 512 * 1024
MAX_VIDEO_BYTES = 256 * 1024
STICKER_SIZE = 512
MAX_VIDEO_SECONDS = 3

# ---- admin-editable settings: hardcoded fallbacks, live values in Redis ----
DEFAULT_SETTINGS = {
    "start_text": (
        "<b>Xtickerz</b>\n"
        "<blockquote>Turn any file into a sticker. Fast. Simple. No editing.</blockquote>\n"
        "Tap Create to make a new pack, or just send a file."
    ),
    "start_image": "",              # telegram file_id, empty = no image
    "force_sub_channel": "@xtickerz",  # empty string = force-sub disabled
    "rate_limit_per_hour": "20",
}
