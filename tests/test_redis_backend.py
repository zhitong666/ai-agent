import asyncio
import json
import os
from unittest.mock import AsyncMock

import pytest

from app.redis_rate_limiter import RedisRateLimiter
from app.redis_session_cache import RedisSessionCache


def test_session_cache_returns_redis_value_without_postgres():
    async def scenario():
        redis = AsyncMock()
        postgres = AsyncMock()

        redis.get.return_value = json.dumps(
            [
                {"role": "user", "content": "你好"},
                {"role": "assistant", "content": "你好"},
            ],
            ensure_ascii=False,
        )

        store = RedisSessionCache(redis, postgres)
        messages = await store.get_messages("s1")

        assert messages == [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好"},
        ]
        assert postgres.get_messages.await_count == 0
        assert redis.set.await_count == 0

    asyncio.run(scenario())


def test_session_cache_falls_back_to_postgres_and_writes_redis():
    async def scenario():
        redis = AsyncMock()
        postgres = AsyncMock()

        redis.get.return_value = None
        postgres.get_messages.return_value = [
            {"role": "user", "content": "什么是 RAG"},
            {"role": "assistant", "content": "RAG 是检索增强生成"},
        ]

        store = RedisSessionCache(redis, postgres)
        messages = await store.get_messages("s1")

        assert len(messages) == 2
        assert postgres.get_messages.await_count == 1
        assert redis.set.await_count == 1

        key = redis.set.await_args.args[0]
        assert key == "chat:session:s1:messages"

    asyncio.run(scenario())


def test_session_cache_invalidates_cache_after_append():
    async def scenario():
        redis = AsyncMock()
        postgres = AsyncMock()

        store = RedisSessionCache(redis, postgres)
        await store.append_turn("s1", "问题", "答案")

        assert postgres.append_turn.await_count == 1
        assert redis.delete.await_count == 1
        assert redis.delete.await_args.args[0] == "chat:session:s1:messages"

    asyncio.run(scenario())


def test_rate_limiter_allows_until_limit_then_blocks():
    async def scenario():
        redis = AsyncMock()
        redis.eval.side_effect = [1, 2, 3]

        limiter = RedisRateLimiter(redis)

        first = await limiter.allow("chat:rate:s1", limit=2, window_seconds=60)
        second = await limiter.allow("chat:rate:s1", limit=2, window_seconds=60)
        third = await limiter.allow("chat:rate:s1", limit=2, window_seconds=60)

        assert first is True
        assert second is True
        assert third is False

    asyncio.run(scenario())


def test_rate_limiter_uses_atomic_lua_script():
    async def scenario():
        redis = AsyncMock()
        redis.eval.return_value = 1

        limiter = RedisRateLimiter(redis)
        await limiter.allow("chat:rate:s1", limit=5, window_seconds=30)

        script = redis.eval.await_args.args[0]
        assert "INCR" in script
        assert "EXPIRE" in script
        assert redis.eval.await_args.args[2] == "chat:rate:s1"

    asyncio.run(scenario())


def test_redis_integration_requires_test_redis_url():
    url = os.getenv("TEST_REDIS_URL")

    if not url:
        pytest.skip("TEST_REDIS_URL not set")

    async def scenario():
        from app.redis_client import create_redis_client

        redis = create_redis_client(url)
        await redis.set("test-key", "ok", ex=5)
        value = await redis.get("test-key")

        assert value == "ok"

        await redis.aclose()

    asyncio.run(scenario())