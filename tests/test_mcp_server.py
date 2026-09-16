import json

import pytest

from app.mcp_server import (
    McpServerConfig,
    McpToolError,
    build_analyze_jd_prompt,
    build_mcp_server,
    load_required_knowledge_document,
    load_server_config,
)
from app.mcp_tools import (
    build_knowledge_titles_resource,
    load_knowledge_document,
)


def write_knowledge_base(path, documents):
    path.write_text(
        json.dumps(documents, ensure_ascii=False),
        encoding="utf-8",
    )


def test_load_server_config_uses_defaults(monkeypatch):
    for key in [
        "MCP_SERVER_NAME",
        "MCP_SERVER_VERSION",
        "MCP_TRANSPORT",
        "MCP_HOST",
        "MCP_PORT",
        "MCP_LOG_LEVEL",
    ]:
        monkeypatch.delenv(key, raising=False)

    config = load_server_config()

    assert config.name == "ai-job-agent"
    assert config.version == "0.2.0"
    assert config.transport == "stdio"
    assert config.host == "127.0.0.1"
    assert config.port == 8000
    assert config.log_level == "INFO"


def test_load_server_config_rejects_invalid_transport(monkeypatch):
    monkeypatch.setenv("MCP_TRANSPORT", "grpc")

    with pytest.raises(ValueError, match="transport"):
        load_server_config()


def test_load_knowledge_document_finds_title(tmp_path):
    kb_path = tmp_path / "kb.json"
    write_knowledge_base(
        kb_path,
        [
            {
                "id": "doc-python",
                "title": "Python",
                "text": "Python is useful.",
            }
        ],
    )

    document = load_knowledge_document("Python", kb_path)

    assert document is not None
    assert document["id"] == "doc-python"
    assert document["text"] == "Python is useful."


def test_load_required_knowledge_document_raises_mcp_tool_error(tmp_path):
    kb_path = tmp_path / "kb.json"
    write_knowledge_base(kb_path, [])

    with pytest.raises(McpToolError, match="not found"):
        load_required_knowledge_document("Python", kb_path)


def test_build_knowledge_titles_resource(tmp_path):
    kb_path = tmp_path / "kb.json"
    write_knowledge_base(
        kb_path,
        [
            {"title": "Python", "text": "python"},
            {"title": "Docker", "text": "docker"},
        ],
    )

    payload = json.loads(build_knowledge_titles_resource(kb_path))

    assert payload == {"titles": ["Python", "Docker"]}


def test_build_analyze_jd_prompt_returns_messages():
    messages = build_analyze_jd_prompt("某公司招聘 AI Agent 工程师")

    assert messages[0]["role"] == "system"
    assert "AI Agent 求职分析助手" in messages[0]["content"]
    assert messages[1]["role"] == "user"
    assert "某公司招聘 AI Agent 工程师" in messages[1]["content"]


def test_build_analyze_jd_prompt_rejects_empty_jd():
    with pytest.raises(McpToolError, match="jd_text"):
        build_analyze_jd_prompt("   ")


def test_build_mcp_server_returns_mcp_server():
    server = build_mcp_server(
        McpServerConfig(
            name="test-server",
            version="0.2.0",
            transport="stdio",
        )
    )

    assert type(server).__name__ == "MCPServer"