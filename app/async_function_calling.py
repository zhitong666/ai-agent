import asyncio

from openai import APIConnectionError, APITimeoutError, RateLimitError

from app.function_calling import (
    FunctionCallingError,
    _repair_messages,
    extract_required_tool_call,
)
from app.structured_output import StructuredOutputError, parse_and_validate


async def call_required_function_async(
    client,
    messages: list[dict],
    tools: list[dict],
    tool_name: str,
    output_model,
    *,
    model_name: str,
    max_attempts: int = 3,
    retry_delay: float = 0,
    semaphore=None,
):
    last_error = None
    current_messages = list(messages)

    for attempt in range(max_attempts):
        try:
            if semaphore is None:
                response = await client.chat.completions.create(
                    model=model_name,
                    messages=current_messages,
                    tools=tools,
                    tool_choice={
                        "type": "function",
                        "function": {"name": tool_name},
                    },
                )
            else:
                async with semaphore:
                    response = await client.chat.completions.create(
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
                await asyncio.sleep(retry_delay)

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
                    await asyncio.sleep(retry_delay)

    raise FunctionCallingError(
        f"function calling 失败，已尝试 {max_attempts} 次"
    ) from last_error