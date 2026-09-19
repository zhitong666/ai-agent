import asyncio
import random
import time

from openai import APIConnectionError, APITimeoutError, AsyncOpenAI, RateLimitError

from app.config import get_settings
from app.context import count_messages_tokens
from app.cost_tracker import CostTracker, get_default_cost_tracker
from app.model_fallback import get_fallback_models


def create_async_client() -> AsyncOpenAI:
    settings = get_settings()

    return AsyncOpenAI(
        api_key=settings.openai_api_key.get_secret_value(),
        base_url=settings.openai_base_url,
    )


def create_llm_semaphore() -> asyncio.Semaphore:
    return asyncio.Semaphore(get_settings().llm_max_concurrency)


def _usage_tokens(response, messages):
    usage = getattr(response, "usage", None)
    prompt_tokens = getattr(usage, "prompt_tokens", 0)
    completion_tokens = getattr(usage, "completion_tokens", 0)

    if isinstance(prompt_tokens, int) and isinstance(completion_tokens, int):
        return prompt_tokens, completion_tokens

    return count_messages_tokens(messages), 0


async def chat_completion_with_retry_async(
    client,
    *,
    model,
    messages,
    tools=None,
    tool_choice=None,
    max_retries=3,
    timeout=10,
    base_delay=0.1,
    max_delay=1.0,
    stream=False,
    semaphore=None,
    tracker: CostTracker | None = None,
    fallback_models=None,
):
    if fallback_models is None:
        fallback_models = get_fallback_models(model)

    models = [model]
    models.extend(
        item for item in fallback_models if item != model
    )

    effective_tracker = tracker or get_default_cost_tracker()
    last_error = None
    started_at = time.perf_counter()

    for model_name in models:
        for attempt in range(max_retries):
            kwargs = {
                "model": model_name,
                "messages": messages,
                "timeout": timeout,
            }

            if tools is not None:
                kwargs["tools"] = tools

            if tool_choice is not None:
                kwargs["tool_choice"] = tool_choice

            if stream:
                kwargs["stream"] = stream

            try:
                if semaphore is None:
                    response = await client.chat.completions.create(
                        **kwargs
                    )
                else:
                    async with semaphore:
                        response = await client.chat.completions.create(
                            **kwargs
                        )
            except (
                APIConnectionError,
                APITimeoutError,
                RateLimitError,
            ) as exc:
                last_error = exc

                if attempt < max_retries - 1:
                    delay = min(
                        max_delay,
                        base_delay * (2 ** attempt),
                    )
                    jitter = random.uniform(0, delay * 0.25)
                    await asyncio.sleep(delay + jitter)

                continue

            if not stream:
                prompt_tokens, completion_tokens = _usage_tokens(
                    response,
                    messages,
                )
                duration_ms = (time.perf_counter() - started_at) * 1000

                effective_tracker.record(
                    model=model_name,
                    input_tokens=prompt_tokens,
                    output_tokens=completion_tokens,
                    latency_ms=duration_ms,
                )

            return response

    raise RuntimeError(
        f"模型调用失败，已尝试模型 {models}，重试 {max_retries} 次"
    ) from last_error