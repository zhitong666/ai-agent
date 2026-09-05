from unittest.mock import MagicMock, patch

import pytest

from app import react


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


def make_tool_call(call_id, tool_name, arguments):
    tool_call = MagicMock()
    tool_call.id = call_id
    tool_call.function.name = tool_name
    tool_call.function.arguments = arguments
    return tool_call


def make_response(tool_calls):
    message = MagicMock()
    message.content = None
    message.tool_calls = tool_calls

    choice = MagicMock()
    choice.message = message

    response = MagicMock()
    response.choices = [choice]
    return response


# 一次响应里有两个 search_knowledge，两个都要执行，最后第二次模型调用时，messages 里应有两个 role=tool 结果
def test_react_processes_multiple_search_calls_in_one_message():
    multi_response = make_response(
        [
            make_tool_call("call_1", "search_knowledge", '{"query":"FastAPI"}'),
            make_tool_call("call_2", "search_knowledge", '{"query":"RAG"}'),
        ]
    )
    finish_response = make_response(
        [make_tool_call("call_3", "finish", '{"answer":"综合答案"}')]
    )

    with patch.object(
        react.client.chat.completions,
        "create",
        side_effect=[multi_response, finish_response],
    ) as mock_create:
        result = react.run_react_loop("对比 FastAPI 和 RAG", retriever=FakeRetriever())

    assert result.answer == "综合答案"
    assert len(result.steps) == 2
    assert [step.action for step in result.steps] == [
        "search_knowledge",
        "search_knowledge",
    ]

    second_messages = mock_create.call_args_list[1].kwargs["messages"]
    tool_messages = [m for m in second_messages if m["role"] == "tool"]
    assert len(tool_messages) == 2


# 一次响应里同时有 search_knowledge 和 list_knowledge_titles，注册表能按名字分发到不同工具
def test_react_dispatches_different_tools_in_one_message():
    multi_response = make_response(
        [
            make_tool_call("call_1", "search_knowledge", '{"query":"FastAPI"}'),
            make_tool_call("call_2", "list_knowledge_titles", "{}"),
        ]
    )
    finish_response = make_response(
        [make_tool_call("call_3", "finish", '{"answer":"已完成"}')]
    )

    with patch(
        "app.tools._load_knowledge_titles",
        return_value=["FastAPI", "RAG"],
    ), patch.object(
        react.client.chat.completions,
        "create",
        side_effect=[multi_response, finish_response],
    ):
        result = react.run_react_loop("介绍知识库主题", retriever=FakeRetriever())

    assert [step.action for step in result.steps] == [
        "search_knowledge",
        "list_knowledge_titles",
    ]
    assert "FastAPI" in result.steps[0].observation
    assert "FastAPI" in result.steps[1].observation


# 多工具调用里出现未知工具时，循环应立即抛错，不会静默丢掉
def test_react_raises_on_unknown_tool_in_multi_call():
    response = make_response(
        [make_tool_call("call_1", "not_exist", "{}")]
    )

    with patch.object(
        react.client.chat.completions,
        "create",
        return_value=response,
    ):
        with pytest.raises(RuntimeError, match="未知工具"):
            react.run_react_loop("测试", retriever=FakeRetriever(), max_steps=2)