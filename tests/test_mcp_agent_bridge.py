import json
from unittest.mock import Mock, patch

from app.mcp_agent_bridge import (
    build_mcp_agent_system_prompt,
    build_mcp_tool_registry,
    discover_mcp_tool_registry,
)
from app.tools import FINISH_TOOL_NAME


def make_tools():
    return [
        {
            "name": "search_knowledge",
            "description": "Search the knowledge base.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "top_k": {"type": "integer"},
                },
                "required": ["query"],
            },
        },
        {
            "name": "list_knowledge_titles",
            "description": "List knowledge titles.",
            "input_schema": {
                "type": "object",
                "properties": {},
            },
        },
    ]


def test_build_mcp_tool_registry_registers_remote_tools():
    registry = build_mcp_tool_registry(make_tools())

    assert set(registry.tool_names()) == {
        "search_knowledge",
        "list_knowledge_titles",
    }

    schema_names = {
        item["function"]["name"]
        for item in registry.to_openai_tools()
    }

    assert schema_names == {
        "search_knowledge",
        "list_knowledge_titles",
        FINISH_TOOL_NAME,
    }


def test_remote_tool_handler_calls_executor_and_serializes():
    executor = Mock(return_value={"hits": []})
    registry = build_mcp_tool_registry(make_tools(), executor)
    tool = registry.get_tool("search_knowledge")

    result = tool.handler({"query": "FastAPI"}, retriever=None)

    executor.assert_called_once_with(
        "search_knowledge",
        {"query": "FastAPI"},
    )
    assert json.loads(result) == {"hits": []}


def test_input_field_uses_first_required_property():
    registry = build_mcp_tool_registry(make_tools())

    assert registry.get_tool("search_knowledge").input_field == "query"
    assert registry.get_tool("list_knowledge_titles").input_field == ""


def test_build_mcp_agent_system_prompt_lists_tools_and_finish():
    prompt = build_mcp_agent_system_prompt(make_tools())

    assert "search_knowledge" in prompt
    assert "list_knowledge_titles" in prompt
    assert "finish" in prompt


def test_discover_mcp_tool_registry_returns_tools_and_registry():
    tools = make_tools()

    with patch(
        "app.mcp_agent_bridge.list_mcp_tools_sync",
        return_value=tools,
    ):
        discovered, registry = discover_mcp_tool_registry()

    assert discovered == tools
    assert set(registry.tool_names()) == {
        "search_knowledge",
        "list_knowledge_titles",
    }