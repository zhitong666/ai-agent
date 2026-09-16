import json

import pytest

from app.mcp_tools import (
    KnowledgeSearchResult,
    McpTool,
    McpToolCatalog,
    build_job_knowledge_mcp_tools,
    list_knowledge_titles,
    search_knowledge,
)


class FakeRetriever:
    def __init__(self, results):
        self.results = results

    def retrieve(self, query, top_k=3):
        return self.results[:top_k]


def make_retrieval_result(chunk_id, title, text, score):
    return {
        "doc": {
            "chunk_id": chunk_id,
            "title": title,
            "text": text,
        },
        "score": score,
    }


def test_search_knowledge_returns_structured_hits():
    retriever = FakeRetriever([
        make_retrieval_result(
            "doc-python-0",
            "Python",
            "FastAPI is a Python framework.",
            0.9,
        ),
        make_retrieval_result(
            "doc-docker-0",
            "Docker",
            "Docker packages applications.",
            0.7,
        ),
    ])

    result = search_knowledge("FastAPI", top_k=2, retriever=retriever)

    assert isinstance(result, KnowledgeSearchResult)
    assert result.query == "FastAPI"
    assert result.count == 2
    assert result.hits[0].chunk_id == "doc-python-0"
    assert result.hits[0].score == pytest.approx(0.9)


def test_search_knowledge_rejects_empty_query():
    with pytest.raises(ValueError, match="query"):
        search_knowledge("   ", retriever=FakeRetriever([]))


def test_search_knowledge_rejects_invalid_top_k():
    with pytest.raises(ValueError, match="top_k"):
        search_knowledge("FastAPI", top_k=0, retriever=FakeRetriever([]))


def test_list_knowledge_titles_reads_knowledge_base(tmp_path):
    kb_path = tmp_path / "kb.json"
    kb_path.write_text(
        json.dumps([
            {"title": "Python", "text": "python text"},
            {"title": "Docker", "text": "docker text"},
        ]),
        encoding="utf-8",
    )

    assert list_knowledge_titles(kb_path) == ["Python", "Docker"]


def test_catalog_rejects_duplicate_tool():
    catalog = McpToolCatalog()
    tool = McpTool(
        name="ping",
        description="ping",
        input_schema={"type": "object", "properties": {}},
        handler=lambda: "pong",
    )
    catalog.register(tool)

    with pytest.raises(ValueError, match="duplicate"):
        catalog.register(tool)


def test_catalog_converts_to_openai_tool_schema():
    catalog = build_job_knowledge_mcp_tools()
    schemas = catalog.to_openai_tools()

    assert set(catalog.names()) == {
        "search_knowledge",
        "list_knowledge_titles",
    }

    search_schema = next(
        item for item in schemas
        if item["function"]["name"] == "search_knowledge"
    )

    assert search_schema["type"] == "function"
    assert set(search_schema["function"]["parameters"]["required"]) == {"query"}
    assert search_schema["function"]["parameters"]["properties"]["top_k"]["type"] == "integer"