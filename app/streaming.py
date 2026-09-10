import asyncio
from collections.abc import AsyncIterator


# 负责生成一条合法 SSE 事件
def sse_event(event: str | None, data: str) -> str:
    lines = []

    if event is not None:
        lines.append(f"event: {event}")

    for line in data.splitlines() or [""]: # 会把包含换行的内容拆成多个 data: 行
        lines.append(f"data: {line}")

    return "\n".join(lines) + "\n\n"


# 是一个异步生成器，调用时不会一次性执行完，而是每次 yield 一块内容
async def text_chunk_stream(
    text: str,
    *,
    chunk_size: int = 5, # 默认 5，是为了方便测试和看到分块效果
    delay: float = 0, # 默认 0，测试时不会等待；真实接入模型流时可以传入真实延迟
) -> AsyncIterator[str]:
    for start in range(0, len(text), chunk_size):
        chunk = text[start : start + chunk_size]
        yield sse_event("chunk", chunk) 

        if delay:
            await asyncio.sleep(delay)

    yield sse_event("done", "")

