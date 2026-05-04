from typing import Optional

try:
    import redis
except ImportError:  # pragma: no cover - optional dependency
    redis = None

from app.core.config import get_settings


def get_redis_client() -> Optional["redis.Redis"]:
    settings = get_settings()
    if not settings.redis_enabled or redis is None:
        return None
    try:
        return redis.from_url(settings.redis_url, decode_responses=True)
    except Exception:
        return None
