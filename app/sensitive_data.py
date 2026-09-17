import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SENSITIVE_PATTERNS = (
    (
        "email",
        re.compile(
            r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
        ),
    ),
    (
        "phone",
        re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    ),
    (
        "id_card",
        re.compile(r"\b\d{17}[\dXx]\b"),
    ),
    (
        "api_key",
        re.compile(
            r"(?i)(api[_-]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_\-]{8,}"
        ),
    ),
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def mask_text(text: str) -> str:
    for name, pattern in SENSITIVE_PATTERNS:
        text = pattern.sub(f"[REDACTED_{name.upper()}]", text)

    return text


def mask_value(value: Any) -> Any:
    if isinstance(value, str):
        return mask_text(value)

    if isinstance(value, dict):
        return {
            key: mask_value(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [mask_value(item) for item in value]

    return value


class AuditLogger:
    def __init__(self):
        self._events: list[dict] = []

    def record(self, event_type: str, **data) -> None:
        self._events.append(
            {
                "timestamp": _now(),
                "event_type": event_type,
                "data": mask_value(data),
            }
        )

    def list_events(self) -> list[dict]:
        return list(self._events)

    def export_jsonl(self, path: str | Path) -> None:
        with Path(path).open("w", encoding="utf-8") as file:
            for event in self._events:
                file.write(
                    json.dumps(event, ensure_ascii=False) + "\n"
                )


audit_logger = AuditLogger()