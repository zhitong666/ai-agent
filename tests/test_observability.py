import json

from app.observability import (
    ObservabilityStore,
    sse_to_event,
    trace_stream,
)


def make_step_event(tool="search_knowledge"):
    return (
        'event: step\n'
        f'data: {{"tool": "{tool}", "input": "FastAPI", '
        '"observation": "ok"}\n\n'
    )


def test_start_trace_and_record_event():
    store = ObservabilityStore()

    trace_id = store.start_trace("FastAPI 需要掌握什么", trace_id="trace-1")
    store.record(trace_id, "step", tool="search_knowledge")

    trace = store.get_trace(trace_id)

    assert trace is not None
    assert trace.trace_id == "trace-1"
    assert trace.question == "FastAPI 需要掌握什么"
    assert trace.events[0].event_type == "step"
    assert trace.events[0].data["tool"] == "search_knowledge"


def test_event_counts():
    store = ObservabilityStore()
    trace_id = store.start_trace("问题", trace_id="trace-2")

    store.record(trace_id, "step", tool="search_knowledge")
    store.record(trace_id, "step", tool="apply_job")
    store.record(trace_id, "done")

    assert store.event_counts(trace_id) == {"step": 2, "done": 1}


def test_export_jsonl(tmp_path):
    store = ObservabilityStore()
    trace_id = store.start_trace("问题", trace_id="trace-3")
    store.record(trace_id, "step", tool="search_knowledge")

    path = tmp_path / "traces.jsonl"
    store.export_jsonl(path)

    lines = path.read_text(encoding="utf-8").strip().splitlines()
    payload = json.loads(lines[0])

    assert payload["trace_id"] == "trace-3"
    assert payload["events"][0]["event_type"] == "step"


def test_sse_to_event_parses_step():
    event_name, data = sse_to_event(make_step_event("apply_job"))

    assert event_name == "step"
    assert data["tool"] == "apply_job"
    assert data["input"] == "FastAPI"


def test_sse_to_event_parses_multiline_answer():
    raw = "event: answer\ndata: 第一行\ndata: 第二行\n\n"

    event_name, data = sse_to_event(raw)

    assert event_name == "answer"
    assert data == "第一行\n第二行"


def test_trace_stream_records_events_and_still_yields():
    store = ObservabilityStore()
    events = [
        make_step_event("search_knowledge"),
        "event: answer\ndata: FastAPI 是后端框架。\n\n",
        "event: done\ndata: \n\n",
    ]

    stream = (event for event in events)
    output = list(trace_stream(store, "问题", "trace-4", stream))

    trace_event = f"event: trace\ndata: trace-4\n\n"
    assert output == [trace_event, *events]

    trace = store.get_trace("trace-4")
    assert trace is not None
    assert [event.event_type for event in trace.events] == [
        "step",
        "answer",
        "done",
    ]