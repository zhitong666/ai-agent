import asyncio
import time

from openai import APIConnectionError, APITimeoutError, RateLimitError

from app.context import count_messages_tokens
from app.cost_tracker import get_default_cost_tracker
from app.function_calling import (
    FunctionCallingError,
    _repair_messages,
    extract_required_tool_call,
)
from app.structured_output import StructuredOutputError, parse_and_validate


def _usage_tokens(response, messages):
    usage = getattr(response, "usage", None)
    prompt_tokens = getattr(usage, "prompt_tokens", 0)
    completion_tokens = getattr(usage, "completion_tokens", 0)

    if isinstance(prompt_tokens, int) and isinstance(completion_tokens, int):
        return prompt_tokens, completion_tokens

    return count_messages_tokens(messages), 0


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
    tracker = get_default_cost_tracker()

    for attempt in range(max_attempts):
        started_at = time.perf_counter()

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

        prompt_tokens, completion_tokens = _usage_tokens(
            response,
            current_messages,
        )
        duration_ms = (time.perf_counter() - started_at) * 1000

        tracker.record(
            model=model_name,
            input_tokens=prompt_tokens,
            output_tokens=completion_tokens,
            latency_ms=duration_ms,
        )

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