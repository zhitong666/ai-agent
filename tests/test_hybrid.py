import numpy as np

from app.rag import HybridRetriever, _normalize


class FakeModel:
    def encode(self, texts, normalize_embeddings=True):
        vectors = {
            "python": [1.0, 0.0, 0.0],
            "docker": [0.0, 1.0, 0.0],
            "rag": [0.0, 0.0, 1.0],
        }
        return np.array([vectors[text] for text in texts])


def test_hybrid_retriever_returns_relevant_document():
    documents = [
        {"id": "doc-python", "title": "Python", "text": "python"},
        {"id": "doc-docker", "title": "Docker", "text": "docker"},
        {"id": "doc-rag", "title": "RAG", "text": "rag"},
    ]

    retriever = HybridRetriever(documents, FakeModel(), alpha=0.5)

    results = retriever.retrieve("python", top_k=1)

    assert results[0]["doc"]["id"] == "doc-python"
    assert "score" in results[0]


def test_normalize_scales_scores_to_zero_one():
    scores = np.array([1.0, 2.0, 3.0])

    normalized = _normalize(scores)

    assert normalized[0] == 0.0
    assert normalized[1] == 0.5
    assert normalized[2] == 1.0


def test_normalize_handles_constant_scores():
    scores = np.array([2.0, 2.0, 2.0])

    normalized = _normalize(scores)

    assert (normalized == 0).all()
