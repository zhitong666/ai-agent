import argparse
import asyncio

import httpx

from benchmarks.http_benchmark import BenchmarkRunner


def parse_headers(raw_headers):
    headers = {}

    for item in raw_headers or []:
        key, value = item.split(":", 1)
        headers[key.strip()] = value.strip()

    return headers


async def main():
    parser = argparse.ArgumentParser(
        description="快速 HTTP 压测工具"
    )
    parser.add_argument("--url", required=True)
    parser.add_argument("--total", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--header", action="append", default=[])
    args = parser.parse_args()

    headers = parse_headers(args.header)

    async with httpx.AsyncClient(timeout=30) as client:
        async def request_once():
            response = await client.get(args.url, headers=headers)
            response.raise_for_status()

        runner = BenchmarkRunner(args.concurrency)
        report = await runner.run(request_once, total=args.total)

    print(f"total={report.total}")
    print(f"success={report.success}")
    print(f"failed={report.failed}")
    print(f"error_rate={report.error_rate:.4f}")
    print(f"throughput_rps={report.throughput_rps:.2f}")
    print(f"avg_ms={report.avg_ms:.2f}")
    print(f"min_ms={report.min_ms:.2f}")
    print(f"max_ms={report.max_ms:.2f}")
    print(f"p50_ms={report.p50_ms:.2f}")
    print(f"p95_ms={report.p95_ms:.2f}")
    print(f"p99_ms={report.p99_ms:.2f}")


if __name__ == "__main__":
    asyncio.run(main())