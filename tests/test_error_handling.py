from unittest.mock import MagicMock, patch

import pytest
from openai import APITimeoutError

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


class BrokenRetriever:
    def retrieve(self, query, top_k=3):
        raise RuntimeError("知识库连接失败")


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


# 第一次超时，第二次成功，create 被调用两次
def test_llm_call_retries_on_timeout_then_succeeds():
    finish_response = make_response("finish", '{"answer":"重试成功"}')
    timeout_error = APITimeoutError("timeout")

    with patch("app.react.time.sleep"), patch.object(
        react.client.chat.completions,
        "create",
        side_effect=[timeout_error, finish_response],
    ) as mock_create:
        result = react.run_react_loop(
            "测试",
            retriever=FakeRetriever(),
            llm_max_retries=2,
        )

    assert result.answer == "重试成功"
    assert mock_create.call_count == 2


# 连续超时后抛出 RuntimeError，且调用次数等于 llm_max_retries
def test_llm_call_raises_after_all_retries():
    timeout_error = APITimeoutError("timeout")

    with patch("app.react.time.sleep"), patch.object(
        react.client.chat.completions,
        "create",
        side_effect=timeout_error,
    ) as mock_create:
        with pytest.raises(RuntimeError, match="模型调用失败"):
            react.run_react_loop(
                "测试",
                retriever=FakeRetriever(),
                llm_max_retries=3,
            )

    assert mock_create.call_count == 3


# 检索器坏了，工具执行失败不会崩溃，而是变成错误文本，模型仍能返回最终答案
def test_tool_error_is_converted_to_observation():
    search_response = make_response("search_knowledge", '{"query":"FastAPI"}')
    finish_response = make_response("finish", '{"answer":"暂时无法检索"}')

    with patch.object(
        react.client.chat.completions,
        "create",
        side_effect=[search_response, finish_response],
    ):
        result = react.run_react_loop("FastAPI", retriever=BrokenRetriever())

    assert result.answer == "暂时无法检索"
    assert len(result.steps) == 1
    assert "执行失败" in result.steps[0].observation
    assert "知识库连接失败" in result.steps[0].observation


# 确认 timeout 参数真的传给了 OpenAI SDK
def test_llm_call_passes_timeout_to_openai():
    finish_response = make_response("finish", '{"answer":"ok"}')

    with patch.object(
        react.client.chat.completions,
        "create",
        return_value=finish_response,
    ) as mock_create:
        react.run_react_loop("测试", retriever=FakeRetriever(), timeout=7)

    assert mock_create.call_args.kwargs["timeout"] == 7