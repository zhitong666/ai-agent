from types import SimpleNamespace

import numpy as np
import pytest
from qdrant_client.models import Filter

from app.vector_store import (
    QdrantStore,
    VectorStoreError,
    _build_qdrant_filter,
    _to_qdrant_payload,
    resolve_vector_store_type,
)


def test_resolve_vector_store_type_normalizes_chroma():
    assert resolve_vector_store_type("CHROMA") == "chroma"


def test_resolve_vector_store_type_normalizes_qdrant():
    assert resolve_vector_store_type(" qdrant ") == "qdrant"


def test_resolve_vector_store_type_rejects_unknown_store():
    with pytest.raises(VectorStoreError, match="未知向量库类型"):
        resolve_vector_store_type("milvus")


def test_to_qdrant_payload_skips_none():
    payload = _to_qdrant_payload(
        {
            "chunk_id": "doc-a-0",
            "source_uri": None,
            "token_count": 3,
        }
    )

    assert payload["token_count"] == 3
    assert "source_uri" not in payload
    assert "chunk_id" not in payload


def test_build_qdrant_filter_returns_none_when_empty():
    assert _build_qdrant_filter(None) is None
    assert _build_qdrant_filter({"source_type": None}) is None


def test_build_qdrant_filter_creates_field_conditions():
    qfilter = _build_qdrant_filter(
        {
            "source_type": "manual",
            "section": "后端",
        }
    )

    assert isinstance(qfilter, Filter)
    assert len(qfilter.must) == 2
    assert {condition.key for condition in qfilter.must} == {
        "source_type",
        "section",
    }


class FakeRecord:
    def __init__(self, record_id, vector, payload):
        self.id = record_id
        self.vector = vector
        self.payload = payload


class FakeQdrantClient:
    def __init__(self, records=None):
        self.records_by_id = records or {}
        self.upserted_points = []
        self.query_calls = []

    def retrieve(
        self,
        collection_name,
        ids=None,
        with_vectors=False,
        with_payload=False,
    ):
        return [
            self.records_by_id[record_id]
            for record_id in ids
            if record_id in self.records_by_id
        ]

    def upsert(self, collection_name, points):
        self.upserted_points.extend(points)

    def query_points(self, **kwargs):
        self.query_calls.append(kwargs)
        return SimpleNamespace(points=[])


def test_qdrant_store_upsert_creates_points():
    client = FakeQdrantClient()
    store = QdrantStore(
        collection_name="test",
        dimension=2,
        client=client,
        create_if_missing=False,
    )

    chunks = [
        {
            "chunk_id": "doc-a-0",
            "text": "python",
            "title": "Python",
        }
    ]
    embeddings = np.array([[1.0, 0.0]])

    store.upsert(chunks, embeddings)

    assert len(client.upserted_points) == 1
    assert client.upserted_points[0].id == "doc-a-0"
    assert client.upserted_points[0].vector == [1.0, 0.0]


def test_qdrant_store_has_chunks_checks_all_ids():
    client = FakeQdrantClient(
        {
            "doc-a-0": FakeRecord("doc-a-0", [1.0, 0.0], {}),
            "doc-a-1": FakeRecord("doc-a-1", [0.0, 1.0], {}),
        }
    )
    store = QdrantStore(
        collection_name="test",
        dimension=2,
        client=client,
        create_if_missing=False,
    )

    assert store.has_chunks(["doc-a-0"]) is True
    assert store.has_chunks(["doc-a-0", "missing"]) is False


def test_qdrant_store_load_embeddings_preserves_order():
    client = FakeQdrantClient(
        {
            "doc-a-1": FakeRecord("doc-a-1", [0.0, 1.0], {}),
            "doc-a-0": FakeRecord("doc-a-0", [1.0, 0.0], {}),
        }
    )
    store = QdrantStore(
        collection_name="test",
        dimension=2,
        client=client,
        create_if_missing=False,
    )

    embeddings = store.load_embeddings(["doc-a-0", "doc-a-1"])

    assert embeddings.tolist() == [[1.0, 0.0], [0.0, 1.0]]


def test_qdrant_store_query_passes_filter():
    client = FakeQdrantClient()
    store = QdrantStore(
        collection_name="test",
        dimension=2,
        client=client,
        create_if_missing=False,
    )

    store.query(
        np.array([1.0, 0.0]),
        top_k=3,
        where={"source_type": "manual"},
    )

    assert client.query_calls[0]["query_filter"] is not None
    assert client.query_calls[0]["limit"] == 3