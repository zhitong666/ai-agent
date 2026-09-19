import logging
import time
import uuid

from opentelemetry import trace
from opentelemetry.propagate import get_global_textmap
from opentelemetry.trace import Status, StatusCode

from app.metrics import metrics
from app.request_context import request_id_var
from app.tracing import get_tracer


logger = logging.getLogger("http")
tracer = get_tracer("ai-job-agent.http")


class ObservabilityMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_path = scope.get("path", "")
        method = scope.get("method", "")

        if request_path == "/metrics":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        carrier = {
            key.decode("latin-1").lower(): value.decode("latin-1")
            for key, value in headers.items()
        }

        request_context = get_global_textmap().extract(carrier)

        raw_request_id = headers.get(b"x-request-id")
        request_id = (
            raw_request_id.decode("utf-8")
            if raw_request_id is not None
            else uuid.uuid4().hex
        )

        token = request_id_var.set(request_id)
        started_at = time.perf_counter()
        status_code = 500

        metrics.enter_request(method=method, path=request_path)

        async def send_wrapper(message):
            nonlocal status_code

            if message["type"] == "http.response.start":
                status_code = message.get("status", 200)

                response_headers = list(message.get("headers", []))
                header_names = {
                    key.lower() for key, _ in response_headers
                }

                if b"x-request-id" not in header_names:
                    response_headers.append(
                        (b"x-request-id", request_id.encode("utf-8"))
                    )

                trace_carrier = {}
                get_global_textmap().inject(trace_carrier)

                for key, value in trace_carrier.items():
                    header_name = key.encode("latin-1")
                    header_value = value.encode("latin-1")

                    if header_name.lower() not in header_names:
                        response_headers.append(
                            (header_name, header_value)
                        )
                        header_names.add(header_name.lower())

                message = {**message, "headers": response_headers}

            await send(message)

        with tracer.start_as_current_span(
            "http.request",
            context=request_context,
            kind=trace.SpanKind.SERVER,
        ) as span:
            span.set_attribute("http.request.method", method)
            span.set_attribute("http.route", request_path)
            span.set_attribute("request_id", request_id)

            try:
                await self.app(scope, receive, send_wrapper)
            except Exception as exc:
                status_code = 500
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR))
                logger.exception(
                    "unhandled request error",
                    extra={
                        "method": method,
                        "request_path": request_path,
                        "status_code": status_code,
                    },
                )
                raise
            else:
                span.set_attribute(
                    "http.response.status_code",
                    status_code,
                )
                span.set_status(
                    Status(StatusCode.ERROR)
                    if status_code >= 500
                    else Status(StatusCode.OK)
                )
            finally:
                duration_ms = (time.perf_counter() - started_at) * 1000

                metrics.exit_request(
                    method=method,
                    path=request_path,
                )
                metrics.observe_http_request(
                    method=method,
                    path=request_path,
                    status_code=status_code,
                    duration_seconds=duration_ms / 1000,
                )

                logger.info(
                    "request completed",
                    extra={
                        "method": method,
                        "request_path": request_path,
                        "status_code": status_code,
                        "duration_ms": round(duration_ms, 3),
                    },
                )

                request_id_var.reset(token)