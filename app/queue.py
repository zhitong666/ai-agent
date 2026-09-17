import os

from arq import create_pool
from arq.connections import RedisSettings


def build_redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(
        os.getenv("REDIS_URL", "redis://localhost:6379/0")
    )


async def create_queue():
    return await create_pool(build_redis_settings())