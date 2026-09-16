import os
from dataclasses import dataclass
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from app.agent import get_retriever
from app.mcp_tools import (
    KnowledgeSearchResult,
    build_knowledge_titles_resource,
    list_knowledge_titles,
    load_knowledge_document,
    search_knowledge,
)

ALLOWED_TRANSPORTS = {"stdio", "sse", "streamable-http"}
ALLOWED_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


@dataclass(frozen=True)
class McpServerConfig:
    name: str = "ai-job-agent"
    version: str = "0.2.0"
    transport: str = "stdio"
    host: str = "127.0.0.1"
    port: int = 8000
    log_level: str = "INFO"
    instructions: str = "AI 求职分析 Agent 的 MCP Server。"


def load_server_config() -> McpServerConfig:
    transport = os.getenv("MCP_TRANSPORT", "stdio").strip().lower()

    if transport not in ALLOWED_TRANSPORTS:
        raise ValueError(f"unsupported MCP transport: {transport}")

    log_level = os.getenv("MCP_LOG_LEVEL", "INFO").strip().upper()

    if log_level not in ALLOWED_LOG_LEVELS:
        raise ValueError(f"unsupported log level: {log_level}")

    port = int(os.getenv("MCP_PORT", "8000"))

    if port < 1 or port > 65535:
        raise ValueError(f"invalid port: {port}")

    return McpServerConfig(
        name=os.getenv("MCP_SERVER_NAME", "ai-job-agent").strip() or "ai-job-agent",
        version=os.getenv("MCP_SERVER_VERSION", "0.2.0").strip() or "0.2.0",
        transport=transport,
        host=os.getenv("MCP_HOST", "127.0.0.1").strip() or "127.0.0.1",
        port=port,
        log_level=log_level,
        instructions="AI 求职分析 Agent 的只读知识库 MCP Server",
    )


class McpToolError(RuntimeError):
    pass


def load_required_knowledge_document(
    title: str,
    path: str | Path | None = None,
) -> dict:
    document = load_knowledge_document(title, path)

    if document is None:
        raise McpToolError(f"knowledge document not found: {title}")

    return document


def build_analyze_jd_prompt(jd_text: str) -> list[dict[str, str]]:
    if not jd_text.strip():
        raise McpToolError("jd_text must not be empty")

    return [
        {
            "role": "system",
            "content": "你是 AI Agent 求职分析助手，请先解析 JD，再分析技能差距。",
        },
        {
            "role": "user",
            "content": f"请分析以下岗位 JD：\n\n{jd_text}",
        },
    ]


def build_mcp_server(
    config: McpServerConfig | None = None,
) -> MCPServer:
    config = config or load_server_config()

    server = MCPServer(
        name=config.name,
        instructions=config.instructions,
        version=config.version,
        log_level=config.log_level,
    )

    @server.tool(
        name="search_knowledge",
        description="Search the AI job knowledge base and return structured hits.",
    )
    def search_knowledge_tool(
        query: str,
        top_k: int = 3,
    ) -> KnowledgeSearchResult:
        return search_knowledge(
            query,
            top_k=top_k,
            retriever=get_retriever(),
        )

    @server.tool(
        name="list_knowledge_titles",
        description="List all available knowledge base titles.",
    )
    def list_knowledge_titles_tool() -> list[str]:
        return list_knowledge_titles()

    @server.tool(
        name="get_knowledge_document",
        description="Read one knowledge document by its title.",
    )
    def get_knowledge_document_tool(title: str) -> dict[str, str]:
        document = load_required_knowledge_document(title)

        return {
            "id": document.get("id", ""),
            "title": document.get("title", ""),
            "text": document.get("text", ""),
        }

    @server.resource(
        "knowledge://titles",
        name="Knowledge titles",
        description="All knowledge base titles as a JSON resource.",
        mime_type="application/json",
    )
    def knowledge_titles_resource() -> str:
        return build_knowledge_titles_resource()

    @server.resource(
        "knowledge://docs/{title}",
        name="Knowledge document",
        description="Read one knowledge document by title.",
        mime_type="application/json",
    )
    def knowledge_document_resource(title: str) -> dict[str, str]:
        document = load_required_knowledge_document(title)

        return {
            "id": document.get("id", ""),
            "title": document.get("title", ""),
            "text": document.get("text", ""),
        }

    @server.prompt(
        name="analyze_jd",
        description="Build a JD analysis prompt for the agent.",
    )
    def analyze_jd_prompt(jd_text: str) -> list[dict[str, str]]:
        return build_analyze_jd_prompt(jd_text)

    return server


def run_server(config: McpServerConfig | None = None) -> None:
    config = config or load_server_config()
    server = build_mcp_server(config)

    if config.transport == "stdio":
        server.run(transport="stdio")
        return

    if config.transport == "sse":
        server.run(
            transport="sse",
            host=config.host,
            port=config.port,
        )
        return

    if config.transport == "streamable-http":
        server.run(
            transport="streamable-http",
            host=config.host,
            port=config.port,
        )
        return

    raise ValueError(f"unsupported transport: {config.transport}")


if __name__ == "__main__":
    run_server()