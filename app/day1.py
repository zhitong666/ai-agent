from typing import TypedDict


class ParsedJob(TypedDict):
    company: str
    title: str


def parse_text(text: str) -> ParsedJob:
    if not text or not text.strip():
        raise ValueError("text must not be empty")

    parts = [part.strip() for part in text.split("|")]

    if len(parts) < 2:
        raise ValueError("expected format: company | title")

    return {
        "company": parts[0],
        "title": parts[1],
    }


if __name__ == "__main__":
    sample = "字节跳动 | AI Agent 工程师"
    result = parse_text(sample)
    print(result)

import asyncio

async def delayed_name(name: str) -> str:
    await asyncio.sleep(0.1)
    return name

async def main() -> None:
    result = await delayed_name("Agent")
    print(result)

if __name__ == "__main__":
    sample = "字节跳动 | AI Agent 工程师"
    print(parse_text(sample))

    asyncio.run(main())
