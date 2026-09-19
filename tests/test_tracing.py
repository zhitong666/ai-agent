import json
import logging

import json
import logging

import pytest
from fastapi.testclient import TestClient
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from app.logging_config import JsonFormatter
from app.main import app
from app.observability import ObservabilityStore, trace_stream
from app.request_context import request_id_var


@pytest.fixture
def tracer_with_exporter():
    old_provider = trace.get_tracer_provider()

    provider = TracerProvider()
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    yield provider.get_tracer("test-tracer"), exporter

    trace.set_tracer_provider(old_provider)


def test_json_formatter_includes_trace_context(tracer_with_exporter):
    tracer, _ = tracer_with_exporter

    with tracer.start_as_current_span("test-span"):
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="hello",
            args=(),
            exc_info=None,
        )
        payload = json.loads(JsonFormatter().format(record))

    assert payload["trace_id"] != "-"
    assert payload["span_id"] != "-"


def test_trace_stream_creates_span_and_events(tracer_with_exporter):
    tracer, exporter = tracer_with_exporter

    store = ObservabilityStore()
    events = [
        'event: step\ndata: {"tool": "search_knowledge", "input": "FastAPI"}\n\n',
        "event: answer\ndata: FastAPI 是后端框架。\n\n",
        "event: done\ndata: \n\n",
    ]

    import app.observability as observability

    original_tracer = observability.tracer
    observability.tracer = tracer

    try:
        output = list(
            trace_stream(
                store,
                "FastAPI 需要掌握什么",
                "trace-1",
                iter(events),
            )
        )
    finally:
        observability.tracer = original_tracer

    spans = exporter.get_finished_spans()

    assert len(output) == 4
    assert spans
    assert spans[0].name == "agent.trace"
    assert spans[0].events[0].name == "step"


def test_http_middleware_injects_traceparent(tracer_with_exporter):
    tracer, _ = tracer_with_exporter

    import app.http_observability as http_observability

    original_tracer = http_observability.tracer
    http_observability.tracer = tracer

    try:
        client = TestClient(app)
        response = client.get("/health")
    finally:
        http_observability.tracer = original_tracer

    assert response.status_code == 200
    assert "traceparent" in response.headers
    assert "x-request-id" in response.headers