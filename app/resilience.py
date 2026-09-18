import asyncio
import random
import time
from dataclasses import dataclass
from enum import Enum


class RetryExhaustedError(RuntimeError):
    pass


class CircuitOpenError(RuntimeError):
    pass


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


# 重试
@dataclass
class RetryConfig:
    max_attempts: int = 3
    base_delay: float = 0.1
    max_delay: float = 1.0
    jitter_ratio: float = 0.25 # 延迟抖动率


# 熔断器
@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 3 # 失败阈值
    cooldown_seconds: float = 5.0 # 冷却时间


async def async_retry(
    operation,
    *,
    config: RetryConfig | None = None,
    retry_exceptions=(Exception,),
    on_retry=None,
):
    config = config or RetryConfig()
    last_error = None

    for attempt in range(config.max_attempts):
        try:
            return await operation()
        except retry_exceptions as exc:
            last_error = exc

            if attempt < config.max_attempts - 1:
                delay = min(
                    config.max_delay,
                    config.base_delay * (2 ** attempt),
                )
                jitter = random.uniform(0, delay * config.jitter_ratio)
                await asyncio.sleep(delay + jitter)

                if on_retry is not None:
                    await on_retry(attempt + 1, exc)

    raise RetryExhaustedError(
        f"operation failed after {config.max_attempts} attempts"
    ) from last_error


# 熔断器
class CircuitBreaker:
    def __init__(
        self,
        config: CircuitBreakerConfig | None = None,
    ):
        self._config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._opened_at = None
        self._half_open_in_flight = False
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        return self._state

    async def call(self, operation):
        await self._before_call()

        try:
            result = await operation()
        except Exception:
            await self._record_failure()
            raise
        else:
            await self._record_success()
            return result

    async def _before_call(self):
        async with self._lock:
            if self._state == CircuitState.CLOSED:
                return

            if self._state == CircuitState.OPEN:
                elapsed = time.monotonic() - self._opened_at

                if elapsed >= self._config.cooldown_seconds:
                    self._state = CircuitState.HALF_OPEN
                else:
                    raise CircuitOpenError("circuit is open")

            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_in_flight:
                    raise CircuitOpenError("half-open probe already running")

                self._half_open_in_flight = True

    async def _record_success(self):
        async with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._half_open_in_flight = False
            self._opened_at = None

    async def _record_failure(self):
        async with self._lock:
            self._failure_count += 1
            self._half_open_in_flight = False

            if self._failure_count >= self._config.failure_threshold:
                self._state = CircuitState.OPEN
                self._opened_at = time.monotonic()


async def with_timeout(operation, timeout: float):
    if timeout is None:
        return await operation()

    return await asyncio.wait_for(operation(), timeout=timeout)


async def run_with_fallback(operation, fallback_value):
    try:
        return await operation()
    except Exception: # noqa: BLE001
        return fallback_value


# 背压
class BackpressureGate:
    def __init__(self, max_concurrency: int):
        self._semaphore = asyncio.Semaphore(max(1, max_concurrency))

    async def run(self, operation):
        async with self._semaphore:
            return await operation()