import hashlib
import json
from typing import Any

import redis.asyncio as aioredis

from app.config import settings

_redis: aioredis.Redis | None = None  # type: ignore[type-arg]

SEARCH_CACHE_TTL = 900  # 15 minutes
MODEL_RESULT_TTL = 86400 * 7  # 7 days


def get_redis() -> aioredis.Redis:  # type: ignore[type-arg]
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis


def _cache_key(prefix: str, data: Any) -> str:
    raw = json.dumps(data, sort_keys=True, default=str)
    digest = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return f"{prefix}:{digest}"


async def get_cached(prefix: str, key_data: Any) -> Any | None:
    try:
        key = _cache_key(prefix, key_data)
        redis = get_redis()
        value = await redis.get(key)
        if value:
            return json.loads(value)
    except Exception:
        pass
    return None


async def set_cached(prefix: str, key_data: Any, value: Any, ttl: int = SEARCH_CACHE_TTL) -> None:
    try:
        key = _cache_key(prefix, key_data)
        redis = get_redis()
        await redis.setex(key, ttl, json.dumps(value, default=str))
    except Exception:
        pass


async def delete_cached(prefix: str, key_data: Any) -> None:
    try:
        key = _cache_key(prefix, key_data)
        redis = get_redis()
        await redis.delete(key)
    except Exception:
        pass
