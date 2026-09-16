import argparse
import asyncio
import json

from app.mcp_client import (
    call_mcp_tool,
    list_mcp_tools,
    mcp_tools_to_openai_schema,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Local MCP client for ai-job-agent",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list-tools")

    search_parser = subparsers.add_parser("search")
    search_parser.add_argument("query")
    search_parser.add_argument("--top-k", type=int, default=3)

    subparsers.add_parser("list-titles")
    subparsers.add_parser("openai-schema")

    return parser


def print_json(value) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


async def run(args: argparse.Namespace) -> None:
    if args.command == "list-tools":
        tools = await list_mcp_tools()
        for tool in tools:
            print(tool["name"])
        return

    if args.command == "search":
        result = await call_mcp_tool(
            "search_knowledge",
            {
                "query": args.query,
                "top_k": args.top_k,
            },
        )
        print_json(result)
        return

    if args.command == "list-titles":
        result = await call_mcp_tool("list_knowledge_titles", {})
        print_json(result)
        return

    if args.command == "openai-schema":
        tools = await list_mcp_tools()
        print_json(mcp_tools_to_openai_schema(tools))


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
