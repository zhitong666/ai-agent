import asyncio
import os
import random

from dotenv import load_dotenv
from openai import APIConnectionError, APITimeoutError, AsyncOpenAI, RateLimitError


def create_async_client() -> AsyncOpenAI:
    load_dotenv()

    return AsyncOpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL"),
    )


def create_llm_semaphore() -> asyncio.Semaphore:
    raw = os.getenv("LLM_MAX_CONCURRENCY", "10") # 大模型最大并发数

    try:
        limit = int(raw)
    except ValueError:
        limit = 10

    return asyncio.Semaphore(max(1, limit))


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

        if stream:
            kwargs["stream"] = stream

        try:
            if semaphore is None:
                return await client.chat.completions.create(**kwargs)

            async with semaphore:
                return await client.chat.completions.create(**kwargs)

        except (APIConnectionError, APITimeoutError, RateLimitError) as exc:
            last_error = exc

            if attempt < max_retries - 1:
                delay = min(max_delay, base_delay * (2 ** attempt))
                jitter = random.uniform(0, delay * 0.25)
                await asyncio.sleep(delay + jitter)

    raise RuntimeError(f"模型调用失败，已重试 {max_retries} 次") from last_error