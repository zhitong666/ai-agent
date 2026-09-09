from unittest.mock import MagicMock, patch

import pytest

from app import react
from app.agent_state import AgentState, load_checkpoint, save_checkpoint


class FakeRetriever:
    def retrieve(self, query, top_k=3):
        return [
            {
                "doc": {
                    "chunk_id": "doc-fastapi-0",
                    "title": "FastAPI",
                    "text": "FastAPI 是 Python 后端框架。",
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


# 验证状态对象能从 running 变成 finished
def test_agent_state_mark_finished():
    state = AgentState(question="测试")

    state.mark_finished("最终答案")

    assert state.status == "finished"
    assert state.final_answer == "最终答案"


# 验证保存后读取，字段保持一致
def test_save_and_load_checkpoint_roundtrip(tmp_path):
    state = AgentState(question="测试", status="running")
    path = tmp_path / "state.json"

    save_checkpoint(state, path)
    loaded = load_checkpoint(path)

    assert loaded.question == "测试"
    assert loaded.status == "running"
    assert loaded.steps == []


# 任务正常结束时，内存状态和 JSON 检查点都标记为完成
def test_run_react_loop_marks_state_finished(tmp_path):
    state = AgentState(question="测试")
    finish_response = make_response("finish", '{"answer":"ok"}')
    path = tmp_path / "state.json"

    with patch.object(
        react.client.chat.completions,
        "create",
        return_value=finish_response,
    ):
        result = react.run_react_loop(
            "测试",
            retriever=FakeRetriever(),
            state=state,
            checkpoint_path=path,
        )

    assert result.answer == "ok"
    assert state.status == "finished"
    assert state.final_answer == "ok"
    assert load_checkpoint(path).final_answer == "ok"


# 检查点里保存了中间步骤
def test_run_react_loop_saves_steps_to_checkpoint(tmp_path):
    state = AgentState(question="FastAPI")
    search_response = make_response("search_knowledge", '{"query":"FastAPI"}')
    finish_response = make_response("finish", '{"answer":"ok"}')
    path = tmp_path / "state.json"

    with patch.object(
        react.client.chat.completions,
        "create",
        side_effect=[search_response, finish_response],
    ):
        react.run_react_loop(
            "FastAPI",
            retriever=FakeRetriever(),
            state=state,
            checkpoint_path=path,
        )

    loaded = load_checkpoint(path)

    assert loaded.status == "finished"
    assert len(loaded.steps) == 1
    assert loaded.steps[0].action == "search_knowledge"


# 超过最大步数时，状态和检查点都标记为失败
def test_run_react_loop_marks_state_failed(tmp_path):
    state = AgentState(question="测试")
    search_response = make_response("search_knowledge", '{"query":"测试"}')
    path = tmp_path / "state.json"

    with patch.object(
        react.client.chat.completions,
        "create",
        return_value=search_response,
    ):
        with pytest.raises(RuntimeError, match="超过最大步数"):
            react.run_react_loop(
                "测试",
                retriever=FakeRetriever(),
                max_steps=2,
                state=state,
                checkpoint_path=path,
            )

    loaded = load_checkpoint(path)

    assert state.status == "failed"
    assert loaded.status == "failed"
    assert len(loaded.steps) == 2