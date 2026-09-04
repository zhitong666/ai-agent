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


# 模型第一次就调用 finish，循环应立即结束，steps 为空
def test_react_finish_without_search():
    response = make_response("finish", '{"answer":"RAG 是检索增强生成。"}')

    with patch.object(
        react.client.chat.completions,
        "create",
        return_value=response,
    ):
        result = react.run_react_loop("什么是 RAG", retriever=FakeRetriever())

    assert result.answer == "RAG 是检索增强生成。"
    assert result.steps == []


# 模型先检索再结束，验证工具结果被追加回消息、步骤被记录、模型被调用了两次
def test_react_search_then_finish():
    search_response = make_response("search_knowledge", '{"query":"什么是 RAG"}')
    finish_response = make_response("finish", '{"answer":"RAG 是检索增强生成。"}')

    with patch.object(
        react.client.chat.completions,
        "create",
        side_effect=[search_response, finish_response],
    ) as mock_create:
        result = react.run_react_loop("什么是 RAG", retriever=FakeRetriever())

    assert result.answer == "RAG 是检索增强生成。"
    assert len(result.steps) == 1
    assert result.steps[0].action == "search_knowledge"
    assert result.steps[0].action_input == "什么是 RAG"
    assert "FastAPI" in result.steps[0].observation
    assert mock_create.call_count == 2

    messages_passed = mock_create.call_args_list[1].kwargs["messages"]
    roles = [message["role"] for message in messages_passed]
    assert "tool" in roles


# 模型一直检索不结束，验证循环在 max_steps=2 后抛出异常，不会无限循环
def test_react_stops_at_max_steps():
    search_response = make_response("search_knowledge", '{"query":"测试"}')

    with patch.object(
        react.client.chat.completions,
        "create",
        return_value=search_response, 
    ) as mock_create:
        with pytest.raises(RuntimeError, match="超过最大步数"):
            react.run_react_loop("测试", retriever=FakeRetriever(), max_steps=2)
    
    assert mock_create.call_count == 2