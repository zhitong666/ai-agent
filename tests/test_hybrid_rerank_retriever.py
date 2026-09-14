import numpy as np

from app.rag import HybridRerankRetriever, rerank


class FakeModel:
    def encode(self, texts, normalize_embeddings=True):
        return np.array(
            [
                [1.0, 0.0] if "python" in text else [0.0, 1.0]
                for text in texts
            ]
        )


class FakeStore:
    def __init__(self, hits=None):
        self.hits = hits or []
        self.query_calls = []

    def query(self, query_embedding, top_k, where=None):
        self.query_calls.append(
            {
                "top_k": top_k,
                "where": where,
            }
        )
        return self.hits


class FakeReranker:
    def __init__(self):
        self.calls = []

    def __call__(self, query, results, top_k):
        self.calls.append(
            {
                "query": query,
                "results": results,
                "top_k": top_k,
            }
        )
        return results[:top_k]


def make_chunks():
    return [
        {"chunk_id": "a", "doc_id": "doc-a", "title": "A", "text": "python"},
        {"chunk_id": "b", "doc_id": "doc-b", "title": "B", "text": "docker"},
        {"chunk_id": "c", "doc_id": "doc-c", "title": "C", "text": "rag"},
        {
            "chunk_id": "d",
            "doc_id": "doc-d",
            "title": "D",
            "text": "python rag",
        },
    ]


def test_hybrid_retriever_merges_vector_and_bm25_candidates():
    chunks = make_chunks()
    store = FakeStore(
        [
            {"id": "c", "score": 1.0},
            {"id": "d", "score": 0.9},
        ]
    )

    retriever = HybridRerankRetriever(
        chunks,
        FakeModel(),
        store,
        candidate_top_k=2,
    )

    results = retriever.retrieve("python", top_k=3)

    ids = {result["doc"]["chunk_id"] for result in results}

    assert ids == {"a", "c", "d"}


def test_hybrid_retriever_passes_filters_to_store():
    chunks = make_chunks()
    store = FakeStore()

    retriever = HybridRerankRetriever(
        chunks,
        FakeModel(),
        store,
    )

    retriever.retrieve(
        "python",
        top_k=3,
        filters={"source_type": "manual"},
    )

    assert store.query_calls[0]["where"] == {"source_type": "manual"}


def test_hybrid_retriever_calls_reranker():
    chunks = make_chunks()
    store = FakeStore(
        [
            {"id": "c", "score": 1.0},
            {"id": "d", "score": 0.9},
        ]
    )
    reranker = FakeReranker()

    retriever = HybridRerankRetriever(
        chunks,
        FakeModel(),
        store,
        reranker=reranker,
        candidate_top_k=2,
    )

    results = retriever.retrieve("python", top_k=2)

    assert len(results) == 2
    assert len(reranker.calls) == 1
    assert reranker.calls[0]["top_k"] == 2

    candidate_ids = {
        result["doc"]["chunk_id"]
        for result in reranker.calls[0]["results"]
    }
    assert candidate_ids == {"a", "c", "d"}


def test_rerank_sorts_by_cross_encoder_scores(monkeypatch):
    class FakeCrossEncoder:
        def predict(self, pairs):
            return np.array([0.2, 0.9, 0.5])

    monkeypatch.setattr(
        "app.rag._get_reranker_model",
        lambda: FakeCrossEncoder(),
    )

    results = [
        {"doc": {"chunk_id": "a", "text": "python"}},
        {"doc": {"chunk_id": "b", "text": "docker"}},
        {"doc": {"chunk_id": "c", "text": "rag"}},
    ]

    ranked = rerank("python", results, top_k=2)

    assert [item["doc"]["chunk_id"] for item in ranked] == ["b", "c"]