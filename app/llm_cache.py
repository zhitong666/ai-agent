import hashlib
import json

from app.redis_cache import RedisCache


def build_cache_key(
    model: str,
    messages: list[dict],
    tools=None,
    tool_choice=None,
) -> str:
    payload = json.dumps(
        {
            "model": model,
            "messages": messages,
            "tools": tools,
            "tool_choice": tool_choice,
        },
        ensure_ascii=False,
        sort_keys=True,
    )

    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"llm:chat:{model}:{digest}"


class LlmCache:
    def __init__(self, redis, default_ttl: int = 300) -> None:
        self._cache = RedisCache(redis)
        self.default_ttl = default_ttl

    async def get(self, key: str):
        return await self._cache.get_json(key)

    async def set(self, key: str, value, ttl: int | None = None) -> None:
        await self._cache.set_json(
            key,
            value,
            ttl or self.default_ttl,
        )

    async def delete(self, key: str) -> None:
        await self._cache.delete(key)