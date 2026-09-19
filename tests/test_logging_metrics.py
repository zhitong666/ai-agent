import json
import logging

from prometheus_client import CollectorRegistry

from app.http_observability import ObservabilityMiddleware
from app.logging_config import JsonFormatter
from app.metrics import Metrics
from app.request_context import get_request_id, new_request_id, request_id_var


def test_json_formatter_outputs_request_id():
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )

    token = request_id_var.set("request-123")
    try:
        payload = json.loads(JsonFormatter().format(record))
    finally:
        request_id_var.reset(token)

    assert payload["message"] == "hello"
    assert payload["request_id"] == "request-123"
    assert payload["level"] == "INFO"


def test_request_context_uses_supplied_id():
    request_id = new_request_id("client-request-1")

    assert request_id == "client-request-1"
    assert get_request_id() == "client-request-1"


def test_metrics_observe_http_request():
    registry = CollectorRegistry()
    metrics = Metrics(registry)

    metrics.enter_request(method="GET", path="/health")
    metrics.exit_request(method="GET", path="/health")
    metrics.observe_http_request(
        method="GET",
        path="/health",
        status_code=200,
        duration_seconds=0.02,
    )

    rendered = metrics.render().decode("utf-8")

    assert "ai_job_agent_http_requests_total" in rendered
    assert 'method="GET"' in rendered
    assert 'status="200"' in rendered


def test_metrics_endpoint_is_prometheus_text():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "ai_job_agent_http_requests_total" in response.text