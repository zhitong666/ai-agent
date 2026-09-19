from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)


class Metrics:
    def __init__(self, registry: CollectorRegistry | None = None) -> None:
        self.registry = registry or CollectorRegistry(auto_describe=True)

        self.http_requests_total = Counter(
            "ai_job_agent_http_requests_total",
            "Total HTTP requests handled by the API.",
            ["method", "path", "status"],
            registry=self.registry,
        )

        self.http_request_duration_seconds = Histogram(
            "ai_job_agent_http_request_duration_seconds",
            "HTTP request duration in seconds.",
            ["method", "path", "status"],
            buckets=(
                0.005,
                0.01,
                0.025,
                0.05,
                0.1,
                0.25,
                0.5,
                1.0,
                2.5,
                5.0,
                10.0,
            ),
            registry=self.registry,
        )

        self.http_inflight_requests = Gauge(
            "ai_job_agent_http_inflight_requests",
            "Current number of in-flight HTTP requests.",
            ["method", "path"],
            registry=self.registry,
        )

    def observe_http_request(
        self,
        *,
        method: str,
        path: str,
        status_code: int,
        duration_seconds: float,
    ) -> None:
        labels = {
            "method": method,
            "path": path,
            "status": str(status_code),
        }

        self.http_requests_total.labels(**labels).inc()
        self.http_request_duration_seconds.labels(**labels).observe(
            duration_seconds
        )

    def enter_request(self, *, method: str, path: str) -> None:
        self.http_inflight_requests.labels(
            method=method,
            path=path,
        ).inc()

    def exit_request(self, *, method: str, path: str) -> None:
        self.http_inflight_requests.labels(
            method=method,
            path=path,
        ).dec()

    def render(self) -> bytes:
        return generate_latest(self.registry)


metrics = Metrics()