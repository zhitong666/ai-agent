from arq import create_pool
from arq.connections import RedisSettings

from app.config import get_settings


def build_redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(get_settings().redis_url)


async def create_queue():
    return await create_pool(build_redis_settings())