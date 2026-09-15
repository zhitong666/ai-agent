import time

from openai import APIConnectionError, APITimeoutError, RateLimitError

def chat_completion_with_retry(
    client,
    *,
    model,
    messages,
    tools=None,
    tool_choice=None,
    max_retries=3,
    timeout=10,
):
    last_error = None

    for attempt in range(max_retries):
        kwargs = {
            "model": model,
            "messages": messages,
            "timeout": timeout,
        }

        if tools is not None:
            kwargs["tools"] = tools
        if tool_choice is not None:
            kwargs["tool_choice"] = tool_choice

        try:
            return client.chat.completions.create(**kwargs)
        except (APIConnectionError, APITimeoutError, RateLimitError) as exc:
            last_error = exc

            if attempt < max_retries - 1:
                time.sleep(0.1 * (attempt + 1))

    raise RuntimeError(f"模型调用失败，已重试 {max_retries} 次") from last_error