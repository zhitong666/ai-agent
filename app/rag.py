import hashlib
import json
import os
from functools import lru_cache
from pathlib import Path

import numpy as np

from app.bm25 import BM25
from app.chunking import chunk_documents
from app.config import get_settings
from app.embedding_registry import (
    get_embedding_model_name,
    get_embedding_profile,
    load_embedding_model,
)
from app.vector_store import build_vector_store


def _collection_name_for_model(model_name: str, dimension: int) -> str:
    digest = hashlib.sha1(model_name.encode("utf-8")).hexdigest()[:8]
    return f"job_knowledge_{dimension}_{digest}"


def load_documents(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


class RAGRetriever:
    def __init__(self, documents: list[dict], model):
        self.documents = documents
        self.model = model
        self.texts = [doc["text"] for doc in documents]
        self.doc_embeddings = model.encode(
            self.texts,
            normalize_embeddings=True,
        )

    def retrieve(self, query: str, top_k: int = 3) -> list[dict]:
        query_embedding = self.model.encode(
            [query],
            normalize_embeddings=True,
        )[0]

        scores = self.doc_embeddings @ query_embedding
        top_indices = np.argsort(scores)[::-1][:top_k]

        return [
            {
                "doc": self.documents[index],
                "score": float(scores[index]),
            }
            for index in top_indices
        ]


def _normalize(scores: np.ndarray) -> np.ndarray:
    scores = np.asarray(scores, dtype=float)
    low = scores.min()
    high = scores.max()

    if high == low:
        return np.zeros_like(scores)

    return (scores - low) / (high - low)


class HybridRetriever:
    def __init__(self, documents: list[dict], model, alpha: float = 0.5):
        self.documents = documents
        self.model = model
        self.alpha = alpha
        self.texts = [doc["text"] for doc in documents]
        self.doc_embeddings = model.encode(
            self.texts,
            normalize_embeddings=True,
        )
        self.bm25 = BM25()
        self.bm25.fit(self.texts)

    def retrieve(self, query: str, top_k: int = 3) -> list[dict]:
        query_embedding = self.model.encode(
            [query],
            normalize_embeddings=True,
        )[0]

        vector_scores = self.doc_embeddings @ query_embedding
        bm25_scores = np.array(self.bm25.score(query))

        final_scores = (
            self.alpha * _normalize(vector_scores)
            + (1 - self.alpha) * _normalize(bm25_scores)
        )

        top_indices = np.argsort(final_scores)[::-1][:top_k]

        return [
            {
                "doc": self.documents[index],
                "score": float(final_scores[index]),
            }
            for index in top_indices
        ]


class PersistentHybridRetriever:
    def __init__(self, chunks, model, store, alpha=0.5):
        self.chunks = chunks
        self.model = model
        self.store = store
        self.alpha = alpha
        self.texts = [chunk["text"] for chunk in chunks]
        self.bm25 = BM25()
        self.bm25.fit(self.texts)

        chunk_ids = [chunk["chunk_id"] for chunk in chunks]

        if self.store.has_chunks(chunk_ids):
            self.doc_embeddings = self.store.load_embeddings(chunk_ids)
        else:
            self.doc_embeddings = model.encode(
                self.texts,
                normalize_embeddings=True,
            )
            self.store.upsert(chunks, self.doc_embeddings)

    def retrieve(self, query, top_k=3):
        query_embedding = self.model.encode(
            [query],
            normalize_embeddings=True,
        )[0]

        vector_scores = self.doc_embeddings @ query_embedding
        bm25_scores = np.array(self.bm25.score(query))

        final_scores = (
            self.alpha * _normalize(vector_scores)
            + (1 - self.alpha) * _normalize(bm25_scores)
        )

        top_indices = np.argsort(final_scores)[::-1][:top_k]

        return [
            {
                "doc": self.chunks[index],
                "score": float(final_scores[index]),
            }
            for index in top_indices
        ]


class HybridRerankRetriever:
    def __init__(
        self,
        chunks,
        model,
        store,
        alpha: float = 0.5,
        candidate_top_k: int = 20,
        reranker=None,
    ):
        self.chunks = chunks
        self.model = model
        self.store = store
        self.alpha = alpha
        self.candidate_top_k = candidate_top_k
        self.reranker = reranker
        self.texts = [chunk["text"] for chunk in chunks]

        self._chunks_by_id = {
            chunk["chunk_id"]: chunk
            for chunk in chunks
        }
        self._index_by_id = {
            chunk["chunk_id"]: index
            for index, chunk in enumerate(chunks)
        }

        self.bm25 = BM25()
        self.bm25.fit(self.texts)

    def retrieve(
        self,
        query: str,
        top_k: int = 3,
        filters: dict | None = None,
    ) -> list[dict]:
        query_embedding = self.model.encode(
            [query],
            normalize_embeddings=True,
        )[0]

        vector_hits = self.store.query(
            query_embedding,
            top_k=self.candidate_top_k,
            where=filters,
        )

        vector_scores = {
            hit["id"]: float(hit["score"])
            for hit in vector_hits
        }

        bm25_scores = np.array(self.bm25.score(query))
        bm25_top_indices = np.argsort(bm25_scores)[::-1][
            : self.candidate_top_k
        ]
        bm25_ids = {
            self.chunks[index]["chunk_id"]
            for index in bm25_top_indices
        }

        union_ids = list(set(vector_scores) | bm25_ids)

        if not union_ids:
            return []

        vector_values = [
            vector_scores.get(chunk_id, 0.0)
            for chunk_id in union_ids
        ]
        bm25_values = [
            bm25_scores[self._index_by_id[chunk_id]]
            for chunk_id in union_ids
        ]

        vector_norm = _normalize(np.array(vector_values))
        bm25_norm = _normalize(np.array(bm25_values))

        combined_scores = (
            self.alpha * vector_norm
            + (1 - self.alpha) * bm25_norm
        )

        candidates = []

        for chunk_id, combined_score in zip(
            union_ids,
            combined_scores,
            strict=False,
        ):
            candidates.append(
                {
                    "doc": self._chunks_by_id[chunk_id],
                    "score": float(combined_score),
                }
            )

        candidates.sort(key=lambda item: item["score"], reverse=True)

        if self.reranker is None:
            return candidates[:top_k]

        return self.reranker(query, candidates, top_k=top_k)


def build_retriever(
    path: Path,
    strategy: str = "semantic",
    chunk_size: int = 120,
    overlap: int = 24,
    embedding_model: str | None = None,
) -> HybridRerankRetriever:
    documents = load_documents(path)
    chunks = chunk_documents(
        documents,
        strategy=strategy,
        chunk_size=chunk_size,
        overlap=overlap,
    )

    settings = get_settings()

    if settings.embedding_provider == "remote":
        model_name = settings.remote_embedding_model
        dimension = settings.remote_embedding_dimension
        model = load_embedding_model(model_name)
    else:
        model_name = get_embedding_model_name(
            "rag_chinese",
            embedding_model or os.getenv("EMBEDDING_MODEL"),
        )
        profile = get_embedding_profile(model_name)
        dimension = profile.dimension
        model = load_embedding_model(model_name)

    collection_name = _collection_name_for_model(
        model_name,
        dimension,
    )

    store_type = os.getenv("VECTOR_STORE", "chroma")
    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")

    store = build_vector_store(
        store_type=store_type,
        collection_name=collection_name,
        dimension=dimension,
        persist_dir="data/chroma",
        qdrant_url=qdrant_url,
    )

    rerank_enabled = os.getenv("RERANK_ENABLED", "true").lower() in {
        "1",
        "true",
        "yes",
    }
    candidate_top_k = int(os.getenv("CANDIDATE_TOP_K", "20"))
    alpha = float(os.getenv("HYBRID_ALPHA", "0.5"))

    return HybridRerankRetriever(
        chunks,
        model,
        store,
        alpha=alpha,
        candidate_top_k=candidate_top_k,
        reranker=rerank if rerank_enabled else None,
    )


@lru_cache(maxsize=1)
def _get_reranker_model():
    from sentence_transformers import CrossEncoder

    return CrossEncoder("BAAI/bge-reranker-base")


def rerank(query: str, results: list[dict], top_k: int = 3) -> list[dict]:
    if not results:
        return []

    pairs = [(query, item["doc"]["text"]) for item in results]
    model = _get_reranker_model()
    scores = model.predict(pairs)
    order = np.argsort(scores)[::-1][:top_k]
    return [results[index] for index in order]