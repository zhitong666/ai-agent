from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from app.function_calling import (
    FunctionCallingError,
    call_required_function,
    extract_required_tool_call,
)
from app.models import JobAnalysis, JobDescription
from app.structured_output import build_tool_parameters_from_model


JD_TOOL = {
    "type": "function",
    "function": {
        "name": "save_job_description",
        "description": "保存解析后的岗位信息",
        "parameters": build_tool_parameters_from_model(JobDescription),
    },
}


def make_tool_call(tool_name, arguments):
    tool_call = MagicMock()
    tool_call.id = "call_test"
    tool_call.function.name = tool_name
    tool_call.function.arguments = arguments
    return tool_call


def make_response(tool_calls):
    message = MagicMock()
    message.tool_calls = tool_calls

    choice = MagicMock()
    choice.message = message

    response = MagicMock()
    response.choices = [choice]
    return response


def test_extract_required_tool_call_returns_expected_call():
    tool_call = make_tool_call("save_job_description", "{}")

    result = extract_required_tool_call(
        make_response([tool_call]).choices[0].message,
        "save_job_description",
    )

    assert result is tool_call


def test_extract_required_tool_call_raises_when_no_tool_calls():
    message = MagicMock()
    message.tool_calls = []

    with pytest.raises(FunctionCallingError, match="没有返回 tool_calls"):
        extract_required_tool_call(message, "save_job_description")


def test_extract_required_tool_call_raises_when_wrong_tool():
    tool_call = make_tool_call("other_tool", "{}")

    with pytest.raises(FunctionCallingError, match="没有调用期望工具"):
        extract_required_tool_call(
            make_response([tool_call]).choices[0].message,
            "save_job_description",
        )


def test_call_required_function_returns_model_on_first_attempt():
    valid_response = make_response(
        [
            make_tool_call(
                "save_job_description",
                '{"company":"测试公司","title":"AI 工程师"}',
            )
        ]
    )

    client = MagicMock()
    client.chat.completions.create.return_value = valid_response

    result = call_required_function(
        client,
        [{"role": "system", "content": "系统提示"}, {"role": "user", "content": "JD"}],
        [JD_TOOL],
        "save_job_description",
        JobDescription,
        model_name="deepseek-chat",
        max_attempts=2,
    )

    assert result.company == "测试公司"
    assert result.title == "AI 工程师"
    assert client.chat.completions.create.call_count == 1


def test_call_required_function_retries_after_invalid_json():
    invalid_response = make_response(
        [make_tool_call("save_job_description", "{bad json")]
    )
    valid_response = make_response(
        [
            make_tool_call(
                "save_job_description",
                '{"company":"测试公司","title":"AI 工程师"}',
            )
        ]
    )

    client = MagicMock()
    client.chat.completions.create.side_effect = [
        invalid_response,
        valid_response,
    ]

    result = call_required_function(
        client,
        [{"role": "system", "content": "系统提示"}, {"role": "user", "content": "JD"}],
        [JD_TOOL],
        "save_job_description",
        JobDescription,
        model_name="deepseek-chat",
        max_attempts=2,
    )

    assert result.company == "测试公司"
    assert client.chat.completions.create.call_count == 2

    second_call_messages = client.chat.completions.create.call_args_list[1].kwargs["messages"]
    assert any(message["role"] == "tool" for message in second_call_messages)
    assert any("参数解析失败" in message["content"] for message in second_call_messages if message["role"] == "tool")


def test_call_required_function_raises_after_all_attempts_fail():
    invalid_response = make_response(
        [make_tool_call("save_job_description", "{bad json")]
    )

    client = MagicMock()
    client.chat.completions.create.side_effect = [
        invalid_response,
        invalid_response,
    ]

    with pytest.raises(FunctionCallingError, match="已尝试 2 次"):
        call_required_function(
            client,
            [{"role": "system", "content": "系统提示"}, {"role": "user", "content": "JD"}],
            [JD_TOOL],
            "save_job_description",
            JobDescription,
            model_name="deepseek-chat",
            max_attempts=2,
        )

    assert client.chat.completions.create.call_count == 2


def test_job_analysis_rejects_empty_summary():
    with pytest.raises(ValidationError):
        JobAnalysis(summary="")