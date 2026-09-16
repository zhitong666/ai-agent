import asyncio
import os
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class McpToolCallError(RuntimeError):
    pass


DEFAULT_SERVER_COMMAND = str(Path(".venv/bin/python"))
DEFAULT_SERVER_ARGS = ("-m", "app.mcp_server")


def _server_parameters(
    command: str,
    args: tuple[str, ...],
) -> StdioServerParameters:
    return StdioServerParameters(
        command=command,
        args=list(args),
        env={**os.environ, "PYTHONPATH": "."},
        cwd=Path.cwd(),
    )


async def list_mcp_tools(
    command: str = DEFAULT_SERVER_COMMAND,
    args: tuple[str, ...] = DEFAULT_SERVER_ARGS,
    timeout: float = 15,
) -> list[dict[str, Any]]:
    params = _server_parameters(command, args)

    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await asyncio.wait_for(
                session.list_tools(),
                timeout=timeout,
            )

    return [
        {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.input_schema,
        }
        for tool in result.tools
    ]


async def call_mcp_tool(
    name: str,
    arguments: dict[str, Any] | None = None,
    command: str = DEFAULT_SERVER_COMMAND,
    args: tuple[str, ...] = DEFAULT_SERVER_ARGS,
    timeout: float = 30,
) -> Any:
    params = _server_parameters(command, args)

    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await asyncio.wait_for(
                session.call_tool(name, arguments or {}),
                timeout=timeout,
            )

    if result.is_error:
        message = "\n".join(
            item.text
            for item in result.content
            if item.type == "text"
        )
        raise McpToolCallError(message or f"MCP tool call failed: {name}")

    if result.structured_content is not None:
        return result.structured_content

    return [
        {
            "type": item.type,
            "text": getattr(item, "text", None),
        }
        for item in result.content
    ]


def mcp_tools_to_openai_schema(
    tools: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description") or "",
                "parameters": tool.get("input_schema")
                or {"type": "object", "properties": {}},
            },
        }
        for tool in tools
    ]


def list_mcp_tools_sync(
    command: str = DEFAULT_SERVER_COMMAND,
    args: tuple[str, ...] = DEFAULT_SERVER_ARGS,
    timeout: float = 15,
) -> list[dict[str, Any]]:
    return asyncio.run(list_mcp_tools(command, args, timeout))


def call_mcp_tool_sync(
    name: str,
    arguments: dict[str, Any] | None = None,
    command: str = DEFAULT_SERVER_COMMAND,
    args: tuple[str, ...] = DEFAULT_SERVER_ARGS,
    timeout: float = 30,
) -> Any:
    return asyncio.run(
        call_mcp_tool(name, arguments, command, args, timeout)
    )
