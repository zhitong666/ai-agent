from app.redis_cache import RedisCache


class RedisSessionCache:
    def __init__(
        self,
        redis,
        postgres_store,
        ttl: int = 300,
    ):
        self._cache = RedisCache(redis)
        self._postgres_store = postgres_store
        self._ttl = ttl

    def _key(self, session_id: str) -> str:
        return f"chat:session:{session_id}:messages"

    async def get_messages(self, session_id: str) -> list[dict]:
        cached = await self._cache.get_json(self._key(session_id))

        if cached is not None:
            return cached

        messages = await self._postgres_store.get_messages(session_id)
        await self._cache.set_json(self._key(session_id), messages, self._ttl)

        return messages

    async def append_turn(
        self,
        session_id: str,
        question: str,
        answer: str,
    ) -> None:
        await self._postgres_store.append_turn(
            session_id,
            question,
            answer,
        )
        await self._cache.delete(self._key(session_id))