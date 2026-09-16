from collections.abc import Callable, Iterator

from app.agent import get_retriever
from app.mcp_agent_bridge import (
    build_mcp_agent_system_prompt,
    build_mcp_tool_registry,
    discover_mcp_tool_registry,
)
from app.react import run_react_loop, stream_react_loop


def _build_registry_and_prompt():
    tools, registry = discover_mcp_tool_registry()

    return registry, build_mcp_agent_system_prompt(tools)


def run_mcp_react_loop(
    question: str,
    retriever=None,
    max_steps: int = 5,
    llm_max_retries: int = 3,
    timeout: int = 10,
    approve_tool_call: Callable[[str, dict], bool] | None = None,
):
    registry, system_prompt = _build_registry_and_prompt()
    retriever = retriever or get_retriever()

    return run_react_loop(
        question,
        retriever=retriever,
        max_steps=max_steps,
        llm_max_retries=llm_max_retries,
        timeout=timeout,
        approve_tool_call=approve_tool_call,
        registry=registry,
        system_prompt=system_prompt,
    )


def stream_mcp_react_loop(
    question: str,
    retriever=None,
    max_steps: int = 5,
    llm_max_retries: int = 3,
    timeout: int = 10,
    approve_tool_call: Callable[[str, dict], bool] | None = None,
    approval_request_id: str | None = None,
) -> Iterator[str]:
    registry, system_prompt = _build_registry_and_prompt()
    retriever = retriever or get_retriever()

    return stream_react_loop(
        question,
        retriever=retriever,
        max_steps=max_steps,
        llm_max_retries=llm_max_retries,
        timeout=timeout,
        approve_tool_call=approve_tool_call,
        approval_request_id=approval_request_id,
        registry=registry,
        system_prompt=system_prompt,
    )