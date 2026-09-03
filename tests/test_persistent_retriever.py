# 核心思路是：PersistentHybridRetriever 的难点不在向量计算，而在于“判断该写入还是该读取”，所以我们用假对象把 Chroma 和 Embedding 模型替换掉，只验证这个判断逻辑。
# 先想清楚为什么用假对象：
# - 真 Chroma 会写磁盘、可能有状态，测试起来慢而且不可控。
# - 真 Embedding 模型会下载、加载很慢。
# - 我们真正要测的是 PersistentHybridRetriever.__init__ 里这条分支：Chroma 有没有这些 id，决定走 encode + upsert，还是走 load_embeddings。
# 所以测试里需要三个假类：
# - FakeModel：代替 Embedding 模型，每次调用记录次数，返回固定向量。
# - FakeCollection：代替 Chroma 的 collection，只提供 get，返回我们预设的已有 id。
# - FakeStore：代替 ChromaStore，记录 upsert 和 load_embeddings 被调用了几次。


import numpy as np 

from app.rag import PersistentHybridRetriever


class FakeModel:
    def __init__(self):
        self.encode_calls = 0

    def encode(self, texts, normalize_embeddings=True):
        self.encode_calls += 1
        return np.array([[1.0, 0.0] for _ in texts])


class FakeCollection:
    def __init__(self, ids):
        self.ids = set(ids)

    def get(self, ids=None, include=None):
        return {"ids": [id_ for id_ in ids if id_ in self.ids]}


class FakeStore:
    def __init__(self, existing_ids):
        self.collection = FakeCollection(existing_ids)
        self.upsert_calls = 0
        self.load_calls = 0

    def upsert(self, chunks, embeddings):
        self.upsert_calls += 1

    def load_embeddings(self, chunk_ids):
        self.load_calls += 1
        return np.array([[1.0, 0.0] for _ in chunk_ids])


def make_chunks():
    return [
        {
            "chunk_id": "doc-a-0",
            "doc_id": "doc-a",
            "title": "A",
            "text": "python",
            "chunk_index": 0,
        },
        {
            "chunk_id": "doc-a-1",
            "doc_id": "doc-a",
            "title": "A",
            "text": "docker",
            "chunk_index": 1,
        },
    ]


# Chroma 里还没有 id，所以必须调用一次 model.encode 和一次 store.upsert，不能走读取
def test_writes_when_chroma_empty():
    model = FakeModel()
    store = FakeStore(existing_ids=[])

    PersistentHybridRetriever(make_chunks(), model, store)

    assert model.encode_calls == 1
    assert store.upsert_calls == 1
    assert store.load_calls == 0



# Chroma 里已经有全部 id，所以不调用 model.encode，直接 load_embeddings。这正是 Day 10 要验证的“重启后不用重新 Embedding”
def test_loads_when_chroma_has_ids():
    model = FakeModel()
    store = FakeStore(existing_ids=["doc-a-0", "doc-a-1"])

    PersistentHybridRetriever(make_chunks(), model, store)

    assert model.encode_calls == 0
    assert store.load_calls == 1
    assert store.upsert_calls == 0


# 确认即使换成持久化版本，返回值仍然是 {"doc", "score"}，并且 BM25 能把包含 python 的 chunk 排到第一
def test_retrieve_returns_doc_and_score():
    model = FakeModel()
    store = FakeStore(existing_ids=["doc-a-0", "doc-a-1"])
    retriever = PersistentHybridRetriever(make_chunks(), model, store)

    results = retriever.retrieve("python", top_k=1)

    assert "doc" in results[0]
    assert "score" in results[0]
    assert results[0]["doc"]["chunk_id"] == "doc-a-0"