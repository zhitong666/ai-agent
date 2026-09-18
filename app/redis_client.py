import redis.asyncio as aioredis

from app.config import get_settings


def build_redis_url() -> str:
    return get_settings().redis_url


def create_redis_client(url: str | None = None):
    return aioredis.from_url(
        url or build_redis_url(),
        decode_responses=True,
    )