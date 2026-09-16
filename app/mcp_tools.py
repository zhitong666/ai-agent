import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class KnowledgeHit(BaseModel):
    chunk_id: str
    title: str
    text: str
    score: float


class KnowledgeSearchResult(BaseModel):
    query: str
    top_k: int
    hits: list[KnowledgeHit] = Field(default_factory=list)
    count: int = 0


@dataclass(frozen=True)
class McpTool:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[..., Any]


class McpToolCatalog:
    def __init__(self) -> None:
        self._tools: dict[str, McpTool] = {}

    def register(self, tool: McpTool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"duplicate tool: {tool.name}")

        self._tools[tool.name] = tool

    def get(self, name: str) -> McpTool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return list(self._tools)

    def to_openai_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.input_schema,
                },
            }
            for tool in self._tools.values()
        ]


DEFAULT_KNOWLEDGE_BASE_PATH = Path("data/knowledge_base.json")


def search_knowledge(
    query: str,
    top_k: int = 3,
    retriever=None,
) -> KnowledgeSearchResult:
    query = query.strip()

    if not query:
        raise ValueError("query must not be empty")

    if top_k < 1 or top_k > 10:
        raise ValueError("top_k must be between 1 and 10")

    if retriever is None:
        raise ValueError("retriever is required")

    results = retriever.retrieve(query, top_k=top_k)
    hits: list[KnowledgeHit] = []

    for item in results:
        doc = item["doc"]
        hits.append(
            KnowledgeHit(
                chunk_id=doc.get("chunk_id", doc.get("id", "unknown")),
                title=doc.get("title", "unknown"),
                text=doc.get("text", ""),
                score=float(item["score"]),
            )
        )

    return KnowledgeSearchResult(
        query=query,
        top_k=top_k,
        hits=hits,
        count=len(hits),
    )


def list_knowledge_titles(
    path: str | Path | None = None,
) -> list[str]:
    path = Path(path) if path is not None else DEFAULT_KNOWLEDGE_BASE_PATH

    with path.open("r", encoding="utf-8") as file:
        documents = json.load(file)

    return [doc["title"] for doc in documents]


def build_job_knowledge_mcp_tools() -> McpToolCatalog:
    catalog = McpToolCatalog()

    catalog.register(
        McpTool(
            name="search_knowledge",
            description="Search the AI job knowledge base and return structured hits.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query",
                    },
                    "top_k": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 10,
                        "default": 3,
                    },
                },
                "required": ["query"],
            },
            handler=search_knowledge,
        )
    )

    catalog.register(
        McpTool(
            name="list_knowledge_titles",
            description="List all available knowledge base titles.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {},
            },
            handler=list_knowledge_titles,
        )
    )

    return catalog
