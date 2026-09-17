import json


# Redis 本身主要存字符串
class RedisCache:
    def __init__(self, redis):
        self._redis = redis

    async def get_json(self, key: str):
        raw = await self._redis.get(key)

        if raw is None:
            return None

        return json.loads(raw)

    # JSON 数据需要序列化后写入，读取后再反序列化
    async def set_json(self, key: str, value, ttl: int) -> None:
        raw = json.dumps(value, ensure_ascii=False)
        await self._redis.set(key, raw, ex=ttl) # ex=ttl 设置过期时间，避免缓存永久堆积

    async def delete(self, key: str) -> None:
        await self._redis.delete(key)