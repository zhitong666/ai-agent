import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from openai import APITimeoutError
from prometheus_client import CollectorRegistry

from app import async_llm
from app.cost_tracker import CostBudgetExceededError, CostTracker
from app.llm_cache import LlmCache, build_cache_key
from app.model_fallback import parse_model_csv


def test_cost_tracker_records_cost_and_tokens():
    tracker = CostTracker(CollectorRegistry())

    tracker.record(
        model="deepseek-chat",
        input_tokens=1000,
        output_tokens=500,
        latency_ms=200,
    )

    assert tracker.total_input_tokens == 1000
    assert tracker.total_output_tokens == 500
    assert round(tracker.total_cost_usd, 6) == round(
        1000 * 0.27 / 1_000_000 + 500 * 1.10 / 1_000_000,
        6,
    )


def test_cost_tracker_enforces_budget():
    tracker = CostTracker(
        CollectorRegistry(),
        budget_usd=0.0001,
    )

    with pytest.raises(CostBudgetExceededError):
        tracker.record(
            model="deepseek-chat",
            input_tokens=1000,
            output_tokens=500,
            latency_ms=100,
        )


def test_build_cache_key_is_stable():
    first = build_cache_key(
        "deepseek-chat",
        [{"role": "user", "content": "hello"}],
    )
    second = build_cache_key(
        "deepseek-chat",
        [{"role": "user", "content": "hello"}],
    )

    assert first == second


def test_llm_cache_get_and_set():
    redis = MagicMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()

    cache = LlmCache(redis, default_ttl=60)

    async def scenario():
        assert await cache.get("key-1") is None

        await cache.set("key-1", {"reply": "ok"})
        redis.set.assert_awaited_once()

    asyncio.run(scenario())


def test_parse_model_csv():
    assert parse_model_csv("deepseek-reasoner, deepseek-chat") == [
        "deepseek-reasoner",
        "deepseek-chat",
    ]
    assert parse_model_csv("") == []


def test_async_llm_records_cost_and_falls_back():
    async def scenario():
        response = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="ok")
                )
            ],
            usage=SimpleNamespace(
                prompt_tokens=10,
                completion_tokens=5,
            ),
        )

        client = MagicMock()
        client.chat.completions.create = AsyncMock(
            side_effect=[
                APITimeoutError("timeout"),
                response,
            ]
        )

        tracker = CostTracker(CollectorRegistry())

        with pytest.MonkeyPatch.context() as monkeypatch:
            monkeypatch.setattr(
                async_llm.asyncio,
                "sleep",
                AsyncMock(),
            )

            result = await async_llm.chat_completion_with_retry_async(
                client,
                model="deepseek-chat",
                messages=[{"role": "user", "content": "hi"}],
                max_retries=1,
                fallback_models=["deepseek-reasoner"],
                tracker=tracker,
            )

        assert result is response
        assert tracker.total_input_tokens == 10
        assert tracker.total_output_tokens == 5
        assert client.chat.completions.create.await_count == 2

        models = [
            call.kwargs["model"]
            for call in client.chat.completions.create.await_args_list
        ]
        assert models == ["deepseek-chat", "deepseek-reasoner"]

    asyncio.run(scenario())