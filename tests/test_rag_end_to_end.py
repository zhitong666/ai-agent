import pytest

from app.rag_evaluate import (
    answer_keyword_coverage,
    evaluate_rag_end_to_end,
    ndcg_at_k,
)


class FakeRetriever:
    def __init__(self, mapping):
        self.mapping = mapping

    def retrieve(self, query, top_k=3):
        return [
            {
                "doc": {"chunk_id": chunk_id},
                "score": 0.9,
            }
            for chunk_id in self.mapping.get(query, [])
        ]


def test_ndcg_at_k_rewards_earlier_relevant_result():
    retrieved = ["a", "b"]
    relevant = ["a"]

    assert ndcg_at_k(retrieved, relevant) == 1.0


def test_ndcg_at_k_penalizes_late_relevant_result():
    retrieved = ["b", "a"]
    relevant = ["a"]

    assert ndcg_at_k(retrieved, relevant) == pytest.approx(
        1.0 / 1.584962500721156,
        abs=1e-6,
    )


def test_answer_keyword_coverage_counts_required_keywords():
    answer = "需要掌握 Python 和 RAG"

    assert answer_keyword_coverage(
        answer,
        ["Python", "RAG"],
    ) == 1.0

    assert answer_keyword_coverage(
        answer,
        ["Python", "Docker"],
    ) == 0.5


def test_answer_keyword_coverage_without_required_keywords():
    assert answer_keyword_coverage("任意答案", []) == 1.0


def test_evaluate_rag_end_to_end_returns_full_report():
    retriever = FakeRetriever(
        {
            "q1": ["a", "x"],
        }
    )

    eval_set = [
        {
            "id": "q1",
            "query": "q1",
            "relevant_chunk_ids": ["a"],
            "required_keywords": ["python"],
            "reference_answer": "需要掌握 python",
        }
    ]

    report = evaluate_rag_end_to_end(
        retriever,
        eval_set,
        top_k=2,
        answer_fn=lambda case, results: "需要掌握 python [a]",
    )

    assert report["avg_recall"] == 1.0
    assert report["avg_precision"] == 0.5
    assert report["avg_ndcg"] == 1.0
    assert report["avg_mrr"] == 1.0
    assert report["avg_keyword_coverage"] == 1.0
    assert report["avg_citation_coverage"] == 1.0