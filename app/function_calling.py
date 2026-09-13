import time

from openai import APIConnectionError, APITimeoutError, RateLimitError

from app.structured_output import StructuredOutputError, parse_and_validate


class FunctionCallingError(RuntimeError):
    """function calling 无法得到可用结果时抛出。"""


# 负责找到期望的工具
def extract_required_tool_call(message, expected_name: str):
    tool_calls = getattr(message, "tool_calls", None)

    if not tool_calls:
        raise FunctionCallingError("模型没有返回 tool_calls")

    for tool_call in tool_calls:
        if tool_call.function.name == expected_name:
            return tool_call

    actual_names = ", ".join(str(call.function.name) for call in tool_calls)
    raise FunctionCallingError(
        f"模型没有调用期望工具 {expected_name}，实际是 {actual_names}"
    )


def _tool_call_payload(tool_call) -> dict:
    return {
        "id": getattr(tool_call, "id", None) or "call_repair",
        "type": "function",
        "function": {
            "name": tool_call.function.name,
            "arguments": tool_call.function.arguments or "{}",
        },
    }


# 会保留原 assistant(tool_calls)，再追加一条 tool 错误消息，让模型看到自己哪里错了
def _repair_messages(messages: list[dict], tool_call, error) -> list[dict]:
    call_id = getattr(tool_call, "id", None) or "call_repair"

    return [
        *messages,
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [_tool_call_payload(tool_call)],
        },
        {
            "role": "tool",
            "tool_call_id": call_id,
            "content": (
                f"工具参数解析失败：{error}。"
                f"请重新调用 {tool_call.function.name}，"
                "输出合法 JSON，并保证字段符合 Schema。"
            ),
        },
    ]


# 把网络错误和结构化输出错误都纳入重试流程
def call_required_function(
    client,
    messages: list[dict],
    tools: list[dict],
    tool_name: str,
    output_model,
    *,
    model_name: str,
    max_attempts: int = 3,
    retry_delay: float = 0,
):
    last_error = None
    current_messages = list(messages)

    for attempt in range(max_attempts):
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=current_messages,
                tools=tools,
                tool_choice={
                    "type": "function",
                    "function": {"name": tool_name},
                },
            )
        except (APIConnectionError, APITimeoutError, RateLimitError) as exc:
            last_error = exc

            if attempt < max_attempts - 1 and retry_delay:
                time.sleep(retry_delay)

            continue

        message = response.choices[0].message
        tool_call = extract_required_tool_call(message, tool_name)

        try:
            return parse_and_validate(
                tool_call.function.arguments,
                output_model,
            )
        except StructuredOutputError as exc:
            last_error = exc

            if attempt < max_attempts - 1:
                current_messages = _repair_messages(
                    current_messages,
                    tool_call,
                    exc,
                )

                if retry_delay:
                    time.sleep(retry_delay)

    raise FunctionCallingError(
        f"function calling 失败，已尝试 {max_attempts} 次"
    ) from last_error
