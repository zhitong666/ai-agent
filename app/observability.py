import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TraceEvent(BaseModel):
    event_type: str
    timestamp: str
    data: dict = Field(default_factory=dict)


class AgentTrace(BaseModel):
    trace_id: str
    question: str
    events: list[TraceEvent] = Field(default_factory=list)


class ObservabilityStore:
    def __init__(self):
        self._traces: dict[str, AgentTrace] = {}

    def start_trace(self, question: str, trace_id: str | None = None) -> str:
        trace_id = trace_id or str(uuid.uuid4())
        self._traces[trace_id] = AgentTrace(
            trace_id=trace_id,
            question=question,
        )
        return trace_id
    
    def record(self, trace_id: str, event_type: str, **data) -> None:
        trace = self._traces.setdefault(
            trace_id,
            AgentTrace(trace_id=trace_id, question=""),
        )
        trace.events.append(
            TraceEvent(
                event_type=event_type,
                timestamp=_now(),
                data=data,
            )
        )

    def get_trace(self, trace_id: str) -> AgentTrace | None:
        return self._traces.get(trace_id)

    def event_counts(self, trace_id: str) -> dict[str, int]:
        trace = self.get_trace(trace_id)

        if trace is None:
            return {}

        counts: dict[str, int] = {}

        for event in trace.events:
            counts[event.event_type] = counts.get(event.event_type, 0) + 1

        return counts

    def export_jsonl(self, path: Path) -> None:
        with path.open("w", encoding="utf-8") as file:
            for trace in self._traces.values():
                file.write(trace.model_dump_json() + "\n")


def sse_to_event(raw_event: str) -> tuple[str, object]:
    event_name = "message"
    data_lines = []

    for line in raw_event.splitlines():
        if line.startswith("event:"):
            event_name = line.removeprefix("event:").strip()
        elif line.startswith("data:"):
            data_lines.append(line.removeprefix("data:").strip())

    text = "\n".join(data_lines)

    if event_name in {"step", "approval"}:
        try:
            data = json.loads(text) if text else {}
        except json.JSONDecodeError:
            data = {"text": text}
    else:
        data = text

    return event_name, data


def trace_stream(store, question, trace_id, stream):
    store.start_trace(question, trace_id)

    yield f"event: trace\ndata: {trace_id}\n\n"

    for raw_event in stream:
        event_name, data = sse_to_event(raw_event)

        if event_name == "step":
            store.record(
                trace_id,
                "step",
                tool=data.get("tool"),
                input=data.get("input"),
                observation=data.get("observation"),
            )
        elif event_name == "approval":
            store.record(
                trace_id,
                "approval",
                tool=data.get("tool"),
                arguments=data.get("arguments"),
            )
        elif event_name == "answer":
            store.record(trace_id, "answer", answer=data)
        elif event_name == "error":
            store.record(trace_id, "error", message=data)
        elif event_name == "done":
            store.record(trace_id, "done")

        yield raw_event

observability_store = ObservabilityStore()
