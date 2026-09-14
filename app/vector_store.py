from typing import Any, Protocol

import chromadb
import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

_METADATA_KEYS = (
    "doc_id",
    "title",
    "chunk_index",
    "source_uri",
    "source_type",
    "section",
    "language",
    "char_count",
    "token_count",
    "content_hash",
    "chunking_version",
    "prev_chunk_id",
    "next_chunk_id",
)


class VectorStoreError(ValueError):
    """向量库配置或操作失败时抛出。"""


class VectorStore(Protocol):
    def upsert(self, chunks: list[dict], embeddings: np.ndarray) -> None:
        ...
    
    def load_embeddings(self, chunk_ids: list[str]) -> np.ndarray:
        ...

    def has_chunks(self, chunk_ids: list[str]) -> bool:
        ...

    def query(
        self,
        query_embedding: np.ndarray,
        top_k: int,
        where: dict | None = None,
    ) -> Any:
        ...


def _to_chroma_metadata(chunk: dict) -> dict:
    metadata = {}

    for key in _METADATA_KEYS:
        value = chunk.get(key)
        if value is None:
            continue
    
        if isinstance(value, (str, int, float, bool)):
            metadata[key] = value
        else:
            metadata[key] = str(value)

    return metadata


def _to_qdrant_payload(chunk: dict) -> dict:
    return _to_chroma_metadata(chunk)


def resolve_vector_store_type(store_type: str) -> str:
    normalized = store_type.strip().lower()

    if normalized not in {"chroma", "qdrant"}:
        raise VectorStoreError(f"未知向量库类型：{store_type}")

    return normalized


def _build_qdrant_filter(
    filter_metadata: dict[str, object] | None,
) -> Filter | None:
    if not filter_metadata:
        return None
    
    conditions = []

    for key, value in filter_metadata.items():
        if value is None:
            continue

        conditions.append(
            FieldCondition(
                key=key,
                match=MatchValue(value=value),
            )
        )

    if not conditions:
        return None
    
    return Filter(must=conditions)

class ChromaStore:
    def __init__(
        self, 
        persist_dir: str, 
        collection_name: str = "job_knowledge"
    ):
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
            # metadata={"hnsw:space": "cosine"} 让 Chroma 用余弦距离，和我们归一化向量做点积的逻辑一致
        )
    
    # upsert 可以重复调用，会覆盖同 id 的数据
    def upsert(self, chunks: list[dict], embeddings: np.ndarray) -> None:
        self.collection.upsert(
            ids=[chunk["chunk_id"] for chunk in chunks],
            documents=[chunk["text"] for chunk in chunks],
            metadatas=[_to_chroma_metadata(chunk) for chunk in chunks],
            embeddings=embeddings.tolist(),
        )

    def load_embeddings(self, chunk_ids: list[str]) -> np.ndarray:
        result = self.collection.get(ids=chunk_ids, include=["embeddings"])
        by_id = dict(zip(result["ids"], result["embeddings"]))
        return np.array([by_id[chunk_id] for chunk_id in chunk_ids])

    def has_chunks(self, chunk_ids: list[str]) -> bool:
        existing_ids = set(self.collection.get(ids=chunk_ids)["ids"])
        return existing_ids == set(chunk_ids)

    def query(
        self, 
        query_embedding: np.ndarray, 
        top_k: int,
        where: dict | None = None,
    ) -> dict:
        kwargs = {
            "query_embeddings": [query_embedding.tolist()],
            "n_results": top_k,
            "include": ["documents", "metadatas", "distances"]
        }
    
        if where:
            kwargs["where"] = _to_chroma_metadata(where)

        return self.collection.query(**kwargs)


class QdrantStore:
    def __init__(
        self,
        collection_name: str,
        dimension: int,
        url: str | None = None,
        client: QdrantClient | None = None,
        create_if_missing: bool = True,
    ):
        self.collection_name = collection_name
        self.dimension = dimension
        self.client = client or QdrantClient(url=url)

        if create_if_missing:
            self._ensure_collection()

    def _ensure_collection(self) -> None:
        collections = self.client.get_collections().collections
        existing_names = {collection.name for collection in collections}

        if self.collection_name in existing_names:
            return

        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(
                size=self.dimension,
                distance=Distance.COSINE,
            ),
        )

    def upsert(self, chunks: list[dict], embeddings: np.ndarray) -> None:
        points = []

        for chunk, embedding in zip(chunks, embeddings):
            points.append(
                PointStruct(
                    id=chunk["chunk_id"],
                    vector=embedding.tolist(),
                    payload=_to_qdrant_payload(chunk),
                )
            )

        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
        )

    def load_embeddings(self, chunk_ids: list[str]) -> np.ndarray:
        records = self.client.retrieve(
            collection_name=self.collection_name,
            ids=chunk_ids,
            with_vectors=True,
            with_payload=False,
        )

        by_id = {
            record.id: np.array(record.vector)
            for record in records
        }

        return np.array([by_id[chunk_id] for chunk_id in chunk_ids])

    def has_chunks(self, chunk_ids: list[str]) -> bool:
        records = self.client.retrieve(
            collection_name=self.collection_name,
            ids=chunk_ids,
            with_vectors=False,
            with_payload=False,
        )

        return len(records) == len(chunk_ids)

    def query(
        self,
        query_embedding: np.ndarray,
        top_k: int,
        where: dict | None = None,
    ) -> list[dict]:
        result = self.client.query_points(
            collection_name=self.collection_name,
            query=query_embedding.tolist(),
            limit=top_k,
            query_filter=_build_qdrant_filter(where),
            with_payload=True,
            with_vectors=False,
        )

        return [
            {
                "id": point.id,
                "score": float(point.score),
                "payload": point.payload,
            }
            for point in result.points
        ]


def build_vector_store(
    store_type: str,
    collection_name: str,
    dimension: int,
    persist_dir = "data/chroma",
    qdrant_url: str = "http://localhost:6333",
) -> VectorStore:
    normalized_type = resolve_vector_store_type(store_type)

    if normalized_type == "chroma":
        return ChromaStore(
            persist_dir=persist_dir,
            collection_name=collection_name,
        )

    return QdrantStore(
        collection_name=collection_name,
        dimension=dimension,
        url=qdrant_url,
    )