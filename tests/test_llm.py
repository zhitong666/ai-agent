from unittest.mock import MagicMock, patch

import pytest

from app import llm

def test_parse_job_description_uses_function_calling():
    tool_call = MagicMock()
    tool_call.function.arguments = (
        '{"company":"字节跳动",'
        '"title":"AI Agent 工程师",'
        '"seniority":"mid",'
        '"responsibilities":[],'
        '"requirements":["Python"],'
        '"keywords":["Agent"],'
        '"domain":""}'
    )

    message = MagicMock()
    message.tool_calls = [tool_call]


    choice = MagicMock()
    choice.message = message

    response = MagicMock()
    response.choices = [choice]

    with patch.object(
        llm.client.chat.completions,
        "create",
        return_value=response,
    ):
        result = llm.parse_job_description("某 JD 文本")

    assert result.company == "字节跳动"
    assert result.title == "AI Agent 工程师"


def test_parse_job_description_raises_when_no_tool_calls():
    message = MagicMock()
    message.tool_calls = []

    choice = MagicMock()
    choice.message = message

    response = MagicMock()
    response.choices = [choice]

    with patch.object(
        llm.client.chat.completions,
        "create",
        return_value=response,
    ):
        with pytest.raises(RuntimeError):
            llm.parse_job_description("某 JD 文本")
