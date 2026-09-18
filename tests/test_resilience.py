import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.resilience import (
    BackpressureGate,
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitOpenError,
    RetryConfig,
    RetryExhaustedError,
    async_retry,
    run_with_fallback,
    with_timeout,
)


def test_async_retry_recovers_after_failures():
    async def scenario():
        attempts = [2]

        async def operation():
            if attempts[0] > 0:
                attempts[0] -= 1
                raise RuntimeError("fail")
            return "ok"

        result = await async_retry(
            operation,
            config=RetryConfig(max_attempts=3),
        )

        assert result == "ok"
        assert attempts == [0]

    asyncio.run(scenario())


def test_async_retry_raises_after_exhausted_attempts():
    async def scenario():
        async def operation():
            raise RuntimeError("always fail")

        with pytest.raises(RetryExhaustedError):
            await async_retry(
                operation,
                config=RetryConfig(max_attempts=2),
            )

    asyncio.run(scenario())


def test_async_retry_uses_async_sleep():
    async def scenario():
        attempts = [1]

        async def operation():
            if attempts[0] > 0:
                attempts[0] -= 1
                raise RuntimeError("fail")
            return "ok"

        with patch(
            "app.resilience.asyncio.sleep",
            new=AsyncMock(),
        ) as sleep:
            await async_retry(operation)

        assert sleep.await_count == 1

    asyncio.run(scenario())


def test_circuit_breaker_opens_after_failures():
    async def scenario():
        breaker = CircuitBreaker(
            CircuitBreakerConfig(
                failure_threshold=2,
                cooldown_seconds=5,
            )
        )

        for _ in range(2):
            with pytest.raises(RuntimeError):
                await breaker.call(lambda: raise_runtime_error())

        with pytest.raises(CircuitOpenError):
            await breaker.call(lambda: asyncio.sleep(0))

    asyncio.run(scenario())


def test_with_timeout_raises_timeout_error():
    async def scenario():
        with pytest.raises(asyncio.TimeoutError):
            await with_timeout(
                lambda: asyncio.sleep(0.1),
                timeout=0.001,
            )

    asyncio.run(scenario())


def test_run_with_fallback_returns_fallback_value():
    async def scenario():
        async def operation():
            raise RuntimeError("fail")

        result = await run_with_fallback(operation, "fallback")

        assert result == "fallback"

    asyncio.run(scenario())


def test_backpressure_gate_limits_concurrency():
    async def scenario():
        active = 0
        peak = 0
        lock = asyncio.Lock()

        async def operation():
            nonlocal active, peak

            async with lock:
                active += 1
                peak = max(peak, active)

            await asyncio.sleep(0.01)

            async with lock:
                active -= 1

        gate = BackpressureGate(max_concurrency=2)

        await asyncio.gather(
            *(gate.run(operation) for _ in range(10))
        )

        assert peak <= 2

    asyncio.run(scenario())


async def raise_runtime_error():
    raise RuntimeError("fail")