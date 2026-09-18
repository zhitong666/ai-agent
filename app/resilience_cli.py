import asyncio

from app.resilience import (
    BackpressureGate,
    CircuitBreaker,
    CircuitBreakerConfig,
    RetryConfig,
    async_retry,
    run_with_fallback,
    with_timeout,
)


async def flaky_operation(attempts: list[int]):
    if attempts and attempts[0] > 0:
        attempts[0] -= 1
        raise RuntimeError("temporary failure")

    return "ok"


async def main():
    attempts = [2]

    result = await async_retry(
        lambda: flaky_operation(attempts),
        config=RetryConfig(max_attempts=3),
    )
    print(f"retry_result={result}")

    breaker = CircuitBreaker(
        CircuitBreakerConfig(
            failure_threshold=2,
            cooldown_seconds=0.1,
        )
    )

    await breaker.call(lambda: asyncio.sleep(0))
    print("breaker_demo=ok")

    fallback_result = await run_with_fallback(
        lambda: with_timeout(lambda: asyncio.sleep(0.01), timeout=0.001),
        "fallback",
    )
    print(f"fallback_result={fallback_result}")

    gate = BackpressureGate(max_concurrency=2)
    gate_result = await gate.run(lambda: asyncio.sleep(0))
    print(f"gate_result={gate_result}")


if __name__ == "__main__":
    asyncio.run(main())