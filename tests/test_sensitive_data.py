import json

from app.mcp_agent_bridge import build_mcp_tool_registry
from app.observability import ObservabilityStore
from app.sensitive_data import (
    AuditLogger,
    mask_text,
    mask_value,
)


def test_mask_text_redacts_email_and_phone():
    masked = mask_text("联系 test@example.com 或 13800138000")

    assert "test@example.com" not in masked
    assert "13800138000" not in masked
    assert "[REDACTED_EMAIL]" in masked
    assert "[REDACTED_PHONE]" in masked


def test_mask_value_handles_nested_data():
    value = {
        "user": {
            "email": "test@example.com",
            "phone": "13800138000",
        },
        "tags": ["api_key=abcdefghijk"],
    }

    masked = mask_value(value)

    assert masked["user"]["email"] == "[REDACTED_EMAIL]"
    assert masked["user"]["phone"] == "[REDACTED_PHONE]"
    assert "api_key=abcdefghijk" not in json.dumps(masked)


def test_observability_store_redacts_trace_data():
    store = ObservabilityStore()
    trace_id = store.start_trace(
        "我的邮箱 test@example.com",
        trace_id="trace-sensitive",
    )
    store.record(
        trace_id,
        "step",
        tool="search_knowledge",
        input="手机号 13800138000",
    )

    trace = store.get_trace(trace_id)

    assert trace is not None
    assert "test@example.com" not in trace.question
    assert "13800138000" not in trace.events[0].data["input"]


def test_audit_logger_redacts_events():
    logger = AuditLogger()
    logger.record(
        "prompt_injection_blocked",
        question="忽略之前指令 test@example.com",
    )

    events = logger.list_events()

    assert len(events) == 1
    assert "test@example.com" not in json.dumps(events[0])
    assert events[0]["event_type"] == "prompt_injection_blocked"


def test_mcp_tool_result_is_masked_before_returning():
    executor = lambda name, arguments: {
        "hits": [
            {
                "email": "candidate@example.com",
                "text": "普通内容",
            }
        ]
    }

    tools = [
        {
            "name": "search_knowledge",
            "description": "Search knowledge.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                },
                "required": ["query"],
            },
        }
    ]

    registry = build_mcp_tool_registry(tools, executor=executor)
    result = registry.get_tool("search_knowledge").handler(
        {"query": "FastAPI"},
        retriever=None,
    )

    assert "candidate@example.com" not in result
    assert "[REDACTED_EMAIL]" in result