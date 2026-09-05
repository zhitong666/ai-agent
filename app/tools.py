import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.agent import format_context

FINISH_TOOL_NAME = "finish"
KNOWLEDGE_BASE_PATH = Path("data/knowledge_base.json")

FINISH_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "finish",
        "description": "已经获得足够信息时，返回最终答案。",
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "answer": {"type": "string", "description": "给用户的最终答案"},
            },
            "required": ["answer"],
        },
    },
}


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    handler: Callable
    input_field: str = "query"


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"工具已注册：{tool.name}")

        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def tool_names(self) -> list[str]:
        return list(self._tools)

    def to_openai_tools(self) -> list[dict]:
        executable_schemas = []

        for tool in self._tools.values():
            executable_schemas.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    },
                }
            )

        return executable_schemas + [FINISH_TOOL_SCHEMA]


def search_knowledge(arguments: dict, retriever) -> str:
    query = arguments.get("query")

    if not query:
        raise ValueError("search_knowledge 需要 query 参数")

    results = retriever.retrieve(query, top_k=3)
    return format_context(results)


def _load_knowledge_titles() -> list[str]:
    with KNOWLEDGE_BASE_PATH.open("r", encoding="utf-8") as file:
        documents = json.load(file)

    return [doc["title"] for doc in documents]


def list_knowledge_titles(arguments: dict, retriever) -> str:
    titles = _load_knowledge_titles()
    return "\n".join(titles)


def build_default_registry() -> ToolRegistry:
    registry = ToolRegistry()

    registry.register(
        Tool(
            name="search_knowledge",
            description="在岗位知识库中检索与用户问题相关的内容。",
            parameters={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "检索关键词或问题",
                    }
                },
                "required": ["query"],
            },
            handler=search_knowledge,
            input_field="query",
        )
    )

    registry.register(
        Tool(
            name="list_knowledge_titles",
            description="列出知识库中已有的学习主题标题。",
            parameters={
                "type": "object",
                "additionalProperties": False,
                "properties": {},
            },
            handler=list_knowledge_titles,
            input_field="",
        )
    )

    return registry