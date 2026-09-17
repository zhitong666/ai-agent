INCR_AND_EXPIRE_SCRIPT = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return current
"""


class RedisRateLimiter:
    def __init__(self, redis):
        self._redis = redis

    async def allow(
        self,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> bool:
        current = await self._redis.eval(
            INCR_AND_EXPIRE_SCRIPT,
            1,
            key,
            window_seconds,
        )

        return int(current) <= limit