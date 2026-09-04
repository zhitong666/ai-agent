from app.evaluate import (
    citation_coverage,
    evaluate_retrieval,
    mrr,
    precision_at_k,
    recall_at_k,
)


def make_results(chunk_ids):
    return [
        {"doc": {"chunk_id": chunk_id}, "score": 0.9}
        for chunk_id in chunk_ids
    ]


class FakeRetriever:
    def __init__(self, mapping):
        self.mapping = mapping
    
    def retrieve(self, query, top_k=3):
        return make_results(self.mapping.get(query, []))


# 召回率等于命中数除以相关总数；相关为空时返回 0
def test_recall_at_k():
    assert recall_at_k(["a", "b", "c"], ["b", "d"]) == 0.5
    assert recall_at_k(["a", "b"], []) == 0.0


# 精确率等于命中数除以检索数；检索为空时返回 0
def test_precision_at_k():
    assert precision_at_k(["a", "b"], ["b", "d"]) == 0.5
    assert precision_at_k([], ["b"]) == 0.0


# 第一条目标排第 1 得 1，第二条排第 2 得 0.5，平均 0.75
def test_mrr():
    retrieved = [
        ["target", "x"],
        ["other", "target2"],
    ]
    relevant = [
        ["target"],
        ["target2"],
    ]

    assert mrr(retrieved, relevant) == 0.75


# 没有命中时该 query 得 0
def test_mrr_returns_zero_when_no_match():
    assert mrr([["x", "y"]], [["z"]]) == 0.0


# evaluate_retrieval 能正确汇总平均召回率、平均精确率和 MRR
def test_evaluate_retrieval():
    retriever = FakeRetriever(
        {
            "q1": ["doc-a-0", "doc-x-0"],
            "q2": ["doc-y-0", "doc-b-0"],
        }
    )
    eval_set = [
        {"query": "q1", "relevant_chunk_ids": ["doc-a-0"]},
        {"query": "q2", "relevant_chunk_ids": ["doc-b-0"]},
    ]

    report = evaluate_retrieval(retriever, eval_set, top_k=2)

    assert report["avg_recall"] == 1.0
    assert report["avg_precision"] == 0.5
    assert report["avg_mrr"] == 0.75


# 回答引用了 [doc-a-0] 和 [doc-unknown]，只有前一个在来源里，所以覆盖率 0.5
def test_citation_coverage():
    reply = "答案是 [doc-a-0] 和 [doc-unknown]"
    source_ids = ["doc-a-0", "doc-b-0"]

    assert citation_coverage(reply, source_ids) == 0.5


# 没有引用时覆盖率为 0
def test_citation_coverage_no_citations():
    assert citation_coverage("没有引用", ["doc-a-0"]) == 0.0