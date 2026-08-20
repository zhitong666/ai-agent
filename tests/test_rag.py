import numpy as np
from app.rag import RAGRetriever

class FakeModel: 
    def encode(self, texts, normalize_embeddings=True):
        vectors = {
            "python": [1.0, 0.0, 0.0],
            "docker": [0.0, 1.0, 0.0],
            "rag": [0.0, 0.0, 1.0],
        }
        return np.array([vectors[text] for text in texts])

def test_retrieve_returns_most_relevant_document():
    documents = [
        {"id": "doc-python", "title": "Python", "text": "python"},
        {"id": "doc-docker", "title": "Docker", "text": "docker"},
        {"id": "doc-rag", "title": "RAG", "text": "rag"},
    ]

    retriever = RAGRetriever(documents, FakeModel())

    results = retriever.retrieve("python", top_k=1)

    assert results[0]["doc"]["id"] == "doc-python"