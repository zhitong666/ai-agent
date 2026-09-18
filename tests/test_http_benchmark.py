import asyncio

from benchmarks.http_benchmark import (
    BenchmarkRunner,
    RequestResult,
    build_report,
    percentile,
)


def test_percentile_returns_expected_value():
    values = [1, 2, 3, 4, 5]

    assert percentile(values, 50) == 3
    assert percentile(values, 95) == 5
    assert percentile([], 95) == 0


def test_build_report_calculates_metrics():
    report = build_report(
        [
            RequestResult(ok=True, duration_ms=10),
            RequestResult(ok=True, duration_ms=20),
            RequestResult(ok=False, duration_ms=30, error="timeout"),
        ]
    )

    assert report.total == 3
    assert report.success == 2
    assert report.failed == 1
    assert report.p50_ms == 20
    assert report.max_ms == 30


def test_benchmark_runner_executes_all_requests():
    async def scenario():
        count = 0

        async def request_once():
            nonlocal count
            count += 1

        runner = BenchmarkRunner(concurrency=3)
        report = await runner.run(request_once, total=20)

        assert count == 20
        assert report.success == 20
        assert report.failed == 0
        assert report.error_rate == 0

    asyncio.run(scenario())


def test_benchmark_runner_records_errors():
    async def scenario():
        async def request_once():
            raise RuntimeError("boom")

        runner = BenchmarkRunner(concurrency=3)
        report = await runner.run(request_once, total=10)

        assert report.failed == 10
        assert report.success == 0
        assert report.error_rate == 1.0

    asyncio.run(scenario())