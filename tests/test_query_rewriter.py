from app.query_rewriter import (
    RewrittenQuery,
    build_rewrite_messages,
    merge_retrieval_results,
    multi_query_retrieve,
    rewrite_query_safe,
)


class FakeRetriever:
    def __init__(self, mapping):
        self.mapping = mapping
        self.calls = []

    def retrieve(self, query, top_k=3):
        self.calls.append((query, top_k))
        return self.mapping.get(query, [])


class BadClient:
    def chat(self):
        raise RuntimeError("fake client error")


def test_build_rewrite_messages_contains_question_and_instruction():
    messages = build_rewrite_messages("FastAPI 是什么")

    assert messages[0]["role"] == "system"
    assert "检索查询改写器" in messages[0]["content"]
    assert messages[1] == {
        "role": "user",
        "content": "用户问题：FastAPI 是什么",
    }


def test_merge_retrieval_results_dedupes_by_highest_score():
    results_by_query = [
        [
            {
                "doc": {"chunk_id": "a", "text": "python"},
                "score": 0.8,
            }
        ],
        [
            {
                "doc": {"chunk_id": "a", "text": "python"},
                "score": 0.9,
            },
            {
                "doc": {"chunk_id": "b", "text": "docker"},
                "score": 0.6,
            },
        ],
    ]

    merged = merge_retrieval_results(results_by_query, top_k=2)

    assert [item["doc"]["chunk_id"] for item in merged] == ["a", "b"]
    assert merged[0]["score"] == 0.9


def test_multi_query_retrieve_falls_back_to_original_query():
    retriever = FakeRetriever(
        {
            "原始问题": [
                {"doc": {"chunk_id": "a"}, "score": 0.7},
            ]
        }
    )

    results = multi_query_retrieve(
        retriever,
        "原始问题",
        top_k=2,
        client=None,
    )

    assert retriever.calls == [("原始问题", 2)]
    assert results[0]["doc"]["chunk_id"] == "a"


def test_multi_query_retrieve_uses_rewritten_queries():
    retriever = FakeRetriever(
        {
            "FastAPI 后端": [
                {"doc": {"chunk_id": "a"}, "score": 0.9},
            ],
            "FastAPI Pydantic": [
                {"doc": {"chunk_id": "b"}, "score": 0.8},
            ],
        }
    )

    plan = RewrittenQuery(
        rewritten_query="FastAPI 后端",
        sub_queries=["FastAPI Pydantic"],
        reason="扩展后端知识点",
    )

    results = multi_query_retrieve(
        retriever,
        "FastAPI 怎么学",
        top_k=2,
        rewrite_fn=lambda question: plan,
    )

    assert [query for query, _ in retriever.calls] == [
        "FastAPI 后端",
        "FastAPI Pydantic",
    ]
    assert [item["doc"]["chunk_id"] for item in results] == ["a", "b"]


def test_rewrite_query_safe_falls_back_on_client_error():
    plan = rewrite_query_safe(
        BadClient(),
        "FastAPI 是什么",
        model_name="deepseek-chat",
        max_attempts=1,
    )

    assert plan.rewritten_query == "FastAPI 是什么"
    assert plan.sub_queries == []