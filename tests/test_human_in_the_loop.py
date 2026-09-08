from unittest.mock import MagicMock, patch

from app import react
from app.tools import build_default_registry


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


# apply_job 的审批标记为 True
def test_apply_job_requires_approval():
    tool = build_default_registry().get_tool("apply_job")

    assert tool.requires_approval is True


# 安全工具不需要审批，正常执行
def test_safe_tool_runs_without_approval():
    search_response = make_response("search_knowledge", '{"query":"FastAPI"}')
    finish_response = make_response("finish", '{"answer":"ok"}')

    with patch.object(
        react.client.chat.completions,
        "create",
        side_effect=[search_response, finish_response],
    ):
        result = react.run_react_loop("FastAPI", retriever=FakeRetriever())

    assert result.answer == "ok"
    assert "FastAPI" in result.steps[0].observation


# 审批回调返回 True，工具真正执行，并拿到参数
def test_apply_job_runs_when_approved():
    apply_response = make_response(
        "apply_job",
        '{"company":"字节跳动","position":"AI Agent 工程师"}',
    )
    finish_response = make_response("finish", '{"answer":"已投递"}')

    approvals = []

    def approve(tool_name, arguments):
        approvals.append((tool_name, arguments))
        return True

    with patch.object(
        react.client.chat.completions,
        "create",
        side_effect=[apply_response, finish_response],
    ):
        result = react.run_react_loop(
            "投递字节跳动 AI Agent 岗位",
            retriever=FakeRetriever(),
            approve_tool_call=approve,
        )

    assert result.answer == "已投递"
    assert len(approvals) == 1
    assert approvals[0][1]["company"] == "字节跳动"
    assert "已投递岗位" in result.steps[0].observation


# 审批回调返回 False，工具不执行，轨迹里显示拒绝
def test_apply_job_skips_when_denied():
    apply_response = make_response(
        "apply_job",
        '{"company":"字节跳动","position":"AI Agent 工程师"}',
    )
    finish_response = make_response("finish", '{"answer":"已取消"}')

    with patch("app.tools.apply_job") as mock_apply, patch.object(
        react.client.chat.completions,
        "create",
        side_effect=[apply_response, finish_response],
    ):
        result = react.run_react_loop(
            "投递字节跳动 AI Agent 岗位",
            retriever=FakeRetriever(),
            approve_tool_call=lambda tool_name, arguments: False,
        )

    assert result.answer == "已取消"
    assert "已被用户拒绝" in result.steps[0].observation
    mock_apply.assert_not_called()


# 没有审批回调时，危险工具不自动执行，轨迹里显示等待人工确认
def test_apply_job_waits_when_no_approval_handler():
    apply_response = make_response(
        "apply_job",
        '{"company":"字节跳动","position":"AI Agent 工程师"}',
    )
    finish_response = make_response("finish", '{"answer":"需要审批"}')

    with patch("app.tools.apply_job") as mock_apply, patch.object(
        react.client.chat.completions,
        "create",
        side_effect=[apply_response, finish_response],
    ):
        result = react.run_react_loop(
            "投递字节跳动 AI Agent 岗位",
            retriever=FakeRetriever(),
        )

    assert result.answer == "需要审批"
    assert "需要人工确认" in result.steps[0].observation
    mock_apply.assert_not_called()