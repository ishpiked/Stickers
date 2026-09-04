"""
Redis-backed state. Nothing here holds media -- only pointers, settings,
and small counters. Jobs are addressed by a uuid that follows the media
through crop -> preview -> emoji -> upload, refreshed with a TTL at each
stage rather than kept forever.
"""
import json
from upstash_redis import Redis
from bot.config import (
    UPSTASH_REDIS_REST_URL, UPSTASH_REDIS_REST_TOKEN,
    PENDING_JOB_TTL, DEFAULT_SETTINGS,
)

redis = Redis(url=UPSTASH_REDIS_REST_URL, token=UPSTASH_REDIS_REST_TOKEN)


# ---------- multi-stage sticker jobs ----------

def save_job(job_id: str, data: dict, ttl: int = PENDING_JOB_TTL) -> None:
    redis.set(f"job:{job_id}", json.dumps(data), ex=ttl)


def get_job(job_id: str) -> dict | None:
    raw = redis.get(f"job:{job_id}")
    return json.loads(raw) if raw else None


def clear_job(job_id: str) -> None:
    redis.delete(f"job:{job_id}")


# ---------- packs ----------

def set_active_pack(user_id: int, pack_name: str) -> None:
    redis.set(f"pack:{user_id}", pack_name, ex=3600)


def get_active_pack(user_id: int) -> str | None:
    return redis.get(f"pack:{user_id}")


def add_user_pack(user_id: int, pack_name: str) -> None:
    redis.sadd(f"packs:{user_id}", pack_name)


def list_user_packs(user_id: int) -> list[str]:
    return list(redis.smembers(f"packs:{user_id}") or [])


# ---------- bans ----------

def is_banned(user_id: int) -> bool:
    return redis.exists(f"ban:{user_id}") == 1


def ban_user(user_id: int) -> None:
    redis.set(f"ban:{user_id}", "1")


def unban_user(user_id: int) -> None:
    redis.delete(f"ban:{user_id}")


# ---------- stats ----------

def bump_stat(name: str) -> None:
    redis.incr(f"stats:{name}")


def get_stat(name: str) -> int:
    val = redis.get(f"stats:{name}")
    return int(val) if val else 0


# ---------- known chats, for broadcast ----------

def remember_chat(chat_id: int) -> None:
    redis.sadd("known_chats", str(chat_id))


def list_chats() -> list[int]:
    return [int(c) for c in (redis.smembers("known_chats") or [])]


# ---------- rate limiting ----------

def check_rate_limit(user_id: int) -> bool:
    """Returns True if the user is still under their hourly cap."""
    limit = int(get_settings()["rate_limit_per_hour"])
    key = f"rl:{user_id}"
    count = redis.incr(key)
    if count == 1:
        redis.expire(key, 3600)
    return count <= limit


# ---------- admin-editable settings ----------

def get_settings() -> dict:
    raw = redis.get("settings:global")
    stored = json.loads(raw) if raw else {}
    return {**DEFAULT_SETTINGS, **stored}


def set_setting(key: str, value: str) -> None:
    data = get_settings()
    data[key] = value
    redis.set("settings:global", json.dumps(data))


def reset_settings() -> None:
    redis.delete("settings:global")
