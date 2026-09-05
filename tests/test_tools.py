from unittest.mock import patch

import pytest

from app import tools
from app.tools import FINISH_TOOL_NAME, Tool, ToolRegistry, build_default_registry

class FakeRetriever:
    def retrieve(self, query, top_k=3):
        return [
            {
                "doc": {
                    "chunk_id": "doc-fastapi-0",
                    "title": "FastAPI",
                    "text": "FastAPI 是 Python 后端框架。",
                },
                "score": 0.9,
            }
        ]


# 默认注册表里至少包含 search_knowledge
def test_build_default_registry_contains_search_knowledge():
    registry = build_default_registry()

    assert "search_knowledge" in registry.tool_names()


# 生成给 DeepSeek 的工具列表里，既有可执行工具，也有 finish。
def test_to_openai_tools_includes_executable_tool_and_finish():
    registry = build_default_registry()

    schemas = registry.to_openai_tools()
    schema_names = {schema["function"]["name"] for schema in schemas}

    assert schema_names == {"search_knowledge", FINISH_TOOL_NAME}


# 直接调用工具函数，验证它能把检索结果格式化成文本
def test_search_knowledge_handler_returns_formatted_context():
    registry = build_default_registry()

    tool = registry.get_tool("search_knowledge")
    observation = tool.handler({"query": "FastAPI"}, retriever=FakeRetriever())

    assert "FastAPI" in observation
    assert "doc-fastapi-0" in observation


# 重复注册同名工具会报错，防止工具名冲突
def test_registry_rejects_duplicate_tool():
    registry = ToolRegistry()

    def echo(arguments, retriever):
        return "ok"

    tool = Tool(
        name="echo",
        description="回显测试",
        parameters={"type": "object", "properties": {}},
        handler=echo,
        input_field="query",
    )

    registry.register(tool)

    with pytest.raises(ValueError, match="已注册"):
        registry.register(tool)


# 查找不存在的工具返回 None，由 ReAct 循环统一处理未知工具错误
def test_registry_returns_none_for_unknown_tool():
    registry = build_default_registry()

    assert registry.get_tool("not_exist") is None