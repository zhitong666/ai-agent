from unittest.mock import patch

from app.tools import build_default_registry, search_knowledge


class FakeRetriever:
    def retrieve(self, query, top_k=3):
        return [
            {
                "doc": {
                    "chunk_id": "doc-rag-0",
                    "title": "RAG",
                    "text": "RAG 是检索增强生成。",
                },
                "score": 0.9,
            }
        ]


def test_search_knowledge_uses_multi_query_retrieve_when_rewrite_enabled():
    fake_client = object()

    with patch(
        "app.tools.multi_query_retrieve",
        return_value=[
            {
                "doc": {
                    "chunk_id": "doc-rag-0",
                    "title": "RAG",
                    "text": "RAG 是检索增强生成。",
                },
                "score": 0.9,
            }
        ],
    ) as mock_retrieve:
        observation = search_knowledge(
            {"query": "RAG 是什么"},
            FakeRetriever(),
            query_rewrite_client=fake_client,
            enable_rewrite=True,
        )

    assert "doc-rag-0" in observation
    assert mock_retrieve.call_args.kwargs["client"] is fake_client
    assert mock_retrieve.call_args.kwargs["enable_rewrite"] is True


def test_search_knowledge_falls_back_to_original_query_when_disabled():
    fake_retriever = FakeRetriever()

    with patch(
        "app.tools.multi_query_retrieve",
        return_value=[
            {
                "doc": {
                    "chunk_id": "doc-rag-0",
                    "title": "RAG",
                    "text": "RAG 是检索增强生成。",
                },
                "score": 0.9,
            }
        ],
    ) as mock_retrieve:
        observation = search_knowledge(
            {"query": "RAG 是什么"},
            fake_retriever,
            query_rewrite_client=None,
            enable_rewrite=False,
        )

    assert "doc-rag-0" in observation
    mock_retrieve.assert_not_called()


def test_build_default_registry_reads_rewrite_env(monkeypatch):
    monkeypatch.setenv("QUERY_REWRITE_ENABLED", "true")

    registry = build_default_registry()
    tool = registry.get_tool("search_knowledge")

    with patch(
        "app.tools.search_knowledge",
        return_value="mocked context",
    ) as mock_handler:
        result = tool.handler(
            {"query": "FastAPI"},
            retriever=FakeRetriever(),
        )

    assert result == "mocked context"
    assert mock_handler.call_args.kwargs["enable_rewrite"] is True