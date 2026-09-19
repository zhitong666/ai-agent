import json
import logging
import sys
from datetime import datetime, timezone

from opentelemetry import trace

from app.config import get_settings
from app.request_context import get_request_id


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        span_context = trace.get_current_span().get_span_context()

        trace_id = (
            format(span_context.trace_id, "032x")
            if span_context.is_valid
            else "-"
        )
        span_id = (
            format(span_context.span_id, "016x")
            if span_context.is_valid
            else "-"
        )

        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": get_request_id(),
            "trace_id": trace_id,
            "span_id": span_id,
        }

        for key in (
            "method",
            "request_path",
            "status_code",
            "duration_ms",
        ):
            value = getattr(record, key, None)

            if value is not None:
                payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    settings = get_settings()
    level = logging.DEBUG if settings.debug else logging.INFO

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True