import asyncio
import time
from dataclasses import dataclass


@dataclass
class RequestResult:
    ok: bool
    duration_ms: float
    error: str | None = None


@dataclass
class BenchmarkReport:
    total: int
    success: int
    failed: int
    error_rate: float
    throughput_rps: float
    avg_ms: float
    min_ms: float
    max_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float


def percentile(sorted_values: list[float], p: float) -> float:
    if not sorted_values:
        return 0.0

    index = min(len(sorted_values) - 1, int((p / 100) * len(sorted_values)))
    return sorted_values[index]


class BenchmarkRunner:
    def __init__(self, concurrency: int = 10):
        self._concurrency = max(1, concurrency)

    async def run(
        self,
        request_fn,
        total: int = 100,
    ) -> BenchmarkReport:
        semaphore = asyncio.Semaphore(self._concurrency)

        async def worker():
            started_at = time.perf_counter()

            async with semaphore:
                try:
                    await request_fn()
                except Exception as exc: # noqa: BLE001
                    duration_ms = (time.perf_counter() - started_at) * 1000
                    return RequestResult(
                        ok=False,
                        duration_ms=duration_ms,
                        error=str(exc),
                    )

            duration_ms = (time.perf_counter() - started_at) * 1000
            return RequestResult(ok=True, duration_ms=duration_ms)

        results = await asyncio.gather(
            *(worker() for _ in range(total))
        )

        return build_report(results)


def build_report(results: list[RequestResult]) -> BenchmarkReport:
    total = len(results)
    success = sum(1 for item in results if item.ok)
    failed = total - success
    durations = sorted(item.duration_ms for item in results)
    total_duration_ms = sum(durations)
    avg_ms = total_duration_ms / total if total else 0.0
    throughput_rps = (success / avg_ms * 1000) if avg_ms else 0.0

    return BenchmarkReport(
        total=total,
        success=success,
        failed=failed,
        error_rate=(failed / total) if total else 0.0,
        throughput_rps=throughput_rps,
        avg_ms=avg_ms,
        min_ms=durations[0] if durations else 0.0,
        max_ms=durations[-1] if durations else 0.0,
        p50_ms=percentile(durations, 50),
        p95_ms=percentile(durations, 95),
        p99_ms=percentile(durations, 99),
    )