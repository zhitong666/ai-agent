from mcp.server.mcpserver import MCPServer

from app.agent import get_retriever
from app.mcp_tools import (
    KnowledgeSearchResult,
    list_knowledge_titles,
    search_knowledge,
)


def build_mcp_server() -> MCPServer:
    server = MCPServer(
        name="ai-job-agent",
        instructions="AI 求职分析 Agent 的只读知识库 MCP Server",
        version="0.1.0",
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

    return server


server = build_mcp_server()


if __name__ == "__main__":
    server.run(transport="stdio")
