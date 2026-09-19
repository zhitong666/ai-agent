import logging
import time
import uuid

from app.metrics import metrics
from app.request_context import request_id_var


logger = logging.getLogger("http")


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

        raw_request_id = dict(scope.get("headers", [])).get(
            b"x-request-id"
        )
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

                headers = list(message.get("headers", []))
                header_names = {key.lower() for key, _ in headers}

                if b"x-request-id" not in header_names:
                    headers.append(
                        (b"x-request-id", request_id.encode("utf-8"))
                    )

                message = {**message, "headers": headers}

            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            status_code = 500
            logger.exception(
                "unhandled request error",
                extra={
                    "method": method,
                    "request_path": request_path,
                    "status_code": status_code,
                },
            )
            raise
        finally:
            duration_ms = (time.perf_counter() - started_at) * 1000

            metrics.exit_request(method=method, path=request_path)
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