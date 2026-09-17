import os

import redis.asyncio as aioredis


def build_redis_url() -> str:
    return os.getenv("REDIS_URL", "redis://localhost:6379/0")


# 客户端复用 TCP 连接，不每次请求都新建连接
def create_redis_client(url: str | None = None):
    # 使用异步 Redis 客户端
    return aioredis.from_url(
        url or build_redis_url(),
        decode_responses=True, # 让 Redis 返回字符串，而不是 bytes
    )