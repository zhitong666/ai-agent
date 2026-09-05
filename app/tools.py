# 负责三件事：
# - 定义工具是什么：名称、描述、参数Schema、执行函数
# - 提供 ToolRegistry：注册工具、查找工具、生成OpenAI工具列表
# - 提供 build_default_registry()：创建当前项目默认工具

from collections.abc import Callable
from dataclasses import dataclass

from app.agent import format_context

FINISH_TOOL_NAME = "finish"

# 不是普通工具，它是“结束循环”的特殊动作，所以单独用 FINISH_TOOL_SCHEMA 表示，不放进注册表
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


# Tool 使用 @dataclass，比普通字典更清晰，每个字段都有明确含义
@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    handler: Callable # 是真正执行工具的函数，参数是模型返回的 arguments 和 retriever
    input_field: str = "query"


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] ={}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"工具已注册：{tool.name}")

        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def tool_names(self) -> list[str]:
        return list(self._tools)

    # 把注册表里的工具 Schema 和 finish Schema 合并后返回给 DeepSeek
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


# 以后新增工具，只需要写一个函数，再在 build_default_registry() 里注册
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
            input_field="query"
        )
    )

    return registry
