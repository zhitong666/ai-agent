import json
from unittest.mock import MagicMock, patch

from app import react
from app.approval import ApprovalStore


class FakeRetriever:
    def retrieve(self, query, top_k=3):
        return [
            {
                "doc": {
                    "chunk_id": "doc-rag-0",
                    "title": "RAG",
                    "text": "RAG 是检索增强生成。",
                },
                "score": 0.9,
            }
        ]


def make_response(tool_name, arguments):
    tool_call = MagicMock()
    tool_call.id = "call_test"
    tool_call.function.name = tool_name
    tool_call.function.arguments = arguments

    message = MagicMock()
    message.content = None
    message.tool_calls = [tool_call]

    choice = MagicMock()
    choice.message = message

    response = MagicMock()
    response.choices = [choice]
    return response


def parse_event_data(event_text: str) -> dict:
    lines = event_text.splitlines()

    for line in lines:
        if line.startswith("data:"):
            return json.loads(line.removeprefix("data:").strip())

    raise AssertionError("SSE 事件中没有 data 字段")


def find_event(events, event_name):
    for event in events:
        if event.startswith(f"event: {event_name}\n"):
            return event

    return None


def test_stream_react_loop_emits_step_answer_and_done():
    search_response = make_response(
        "search_knowledge",
        '{"query":"FastAPI"}',
    )
    finish_response = make_response(
        "finish",
        '{"answer":"FastAPI 是后端框架。"}',
    )

    with patch.object(
        react.client.chat.completions,
        "create",
        side_effect=[search_response, finish_response],
    ):
        events = list(
            react.stream_react_loop(
                "FastAPI 需要掌握什么",
                retriever=FakeRetriever(),
            )
        )

    step_event = find_event(events, "step")
    answer_event = find_event(events, "answer")
    done_event = find_event(events, "done")

    assert step_event is not None
    assert answer_event is not None
    assert done_event is not None

    step = parse_event_data(step_event)
    assert step["tool"] == "search_knowledge"
    assert "FastAPI" in step["input"]


def test_stream_react_loop_emits_approval_and_approves():
    apply_response = make_response(
        "apply_job",
        '{"company":"测试公司","position":"AI 工程师"}',
    )
    finish_response = make_response(
        "finish",
        '{"answer":"已完成投递。"}',
    )

    with patch.object(
        react.client.chat.completions,
        "create",
        side_effect=[apply_response, finish_response],
    ):
        events = list(
            react.stream_react_loop(
                "帮我投递这个岗位",
                retriever=FakeRetriever(),
                approve_tool_call=lambda name, arguments: True,
                approval_request_id="approval-1",
            )
        )

    approval_event = find_event(events, "approval")
    step_event = find_event(events, "step")

    assert approval_event is not None
    assert step_event is not None

    approval = parse_event_data(approval_event)
    assert approval["request_id"] == "approval-1"
    assert approval["tool"] == "apply_job"

    step = parse_event_data(step_event)
    assert "已投递岗位" in step["observation"]


def test_stream_react_loop_emits_approval_and_rejects():
    apply_response = make_response(
        "apply_job",
        '{"company":"测试公司","position":"AI 工程师"}',
    )
    finish_response = make_response(
        "finish",
        '{"answer":"好的，已取消投递。"}',
    )

    with patch.object(
        react.client.chat.completions,
        "create",
        side_effect=[apply_response, finish_response],
    ):
        events = list(
            react.stream_react_loop(
                "帮我投递这个岗位",
                retriever=FakeRetriever(),
                approve_tool_call=lambda name, arguments: False,
                approval_request_id="approval-2",
            )
        )

    step_event = find_event(events, "step")
    step = parse_event_data(step_event)

    assert "已被用户拒绝" in step["observation"]


def test_approval_store_roundtrip():
    store = ApprovalStore()
    store.decide("approval-3", True)

    assert store.wait("approval-3", timeout=0.1) is True


def test_approval_store_times_out_when_no_decision():
    store = ApprovalStore()

    assert store.wait("approval-4", timeout=0.01) is False
