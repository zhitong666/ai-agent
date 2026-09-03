import json 
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

from app.chunking import chunk_documents
from app.bm25 import BM25

from sentence_transformers import CrossEncoder

from app.vector_store import ChromaStore

DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"

# 打开 JSON 文件, 读取并返回 Python 列表
def load_documents(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)

class RAGRetriever:
    # 保存文档，保存模型，把每篇文档的text转成向量
    def __init__(self, documents: list[dict], model):
        self.documents = documents
        self.model = model
        self.texts = [doc["text"] for doc in documents]
        self.doc_embeddings = model.encode(
            self.texts,
            normalize_embeddings=True,
        )

    # 把问题转成向量
    # 用点积计算问题与每篇文档的相似度
    # 使用 np.argsort() 找出分数最高的文档
    # 返回文档和分数
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


# 加一个归一化和混合检索类
def _normalize(scores: np.ndarray) -> np.ndarray:
    scores = np.asarray(scores, dtype=float)
    low = scores.min()
    high = scores.max()
    if high == low:
        return np.zeros_like(scores)
    return (scores - low) / (high - low)

# 向量分和 BM25 分取值范围不同，所以先各自归一化到 0~1，再用 alpha 加权求和。alpha=0.5 表示两边权重一样
class HybridRetriever:
    def __init__(self, documents: list[dict], model, alpha: float = 0.5):
        self.documents = documents
        self.model = model
        self.alpha = alpha
        self.texts = [doc["text"] for doc in documents]
        self.doc_embeddings = model.encode(self.texts, normalize_embeddings=True)
        self.bm25 = BM25()
        self.bm25.fit(self.texts)

    def retrieve(self, query: str, top_k: int = 3) -> list[dict]:
        query_embedding = self.model.encode([query], normalize_embeddings=True)[0]
        vector_scores = self.doc_embeddings @ query_embedding
        bm25_scores = np.array(self.bm25.score(query))

        final_scores = (
            self.alpha * _normalize(vector_scores)
            + (1 - self.alpha) * _normalize(bm25_scores)
        )

        top_indices = np.argsort(final_scores)[::-1][:top_k]

        return [
            {"doc": self.documents[index], "score": float(final_scores[index])}
            for index in top_indices
        ]


# 第一次运行时 Chroma 里没有这些 chunk，就重新 Embedding 并写入；之后再启动时，existing_ids 已经齐全，就直接 load_embeddings，不再重复编码。BM25 因为数据量小，仍保留在内存里
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
        existing_ids = set(self.store.collection.get(ids=chunk_ids)["ids"])

        if existing_ids == set(chunk_ids):
            self.doc_embeddings = self.store.load_embeddings(chunk_ids)
        else:
            self.doc_embeddings = model.encode(self.texts, normalize_embeddings=True)
            self.store.upsert(chunks, self.doc_embeddings)

    def retrieve(self, query, top_k=3):
        query_embedding = self.model.encode([query], normalize_embeddings=True)[0]
        vector_scores = self.doc_embeddings @ query_embedding
        bm25_scores = np.array(self.bm25.score(query))

        final_scores = (
            self.alpha * _normalize(vector_scores)
            + (1 - self.alpha) * _normalize(bm25_scores)
        )

        top_indices = np.argsort(final_scores)[::-1][:top_k]

        return [
            {"doc": self.chunks[index], "score": float(final_scores[index])}
            for index in top_indices
        ]


# 先加载文档，再切块，再编码
# 切换检索入口: 把 build_retriever 的返回值从 RAGRetriever 改成 HybridRetriever
# 修改 build_retriever，让它返回持久化版本
def build_retriever(path: Path, strategy: str = "fixed") -> PersistentHybridRetriever:
    documents = load_documents(path)
    chunks = chunk_documents(documents, strategy=strategy)
    model = SentenceTransformer(DEFAULT_EMBEDDING_MODEL)
    store = ChromaStore(persist_dir="data/chroma")
    return PersistentHybridRetriever(chunks, model, store)


# CrossEncoder 会同时把 query 和候选文本送进模型，比双塔向量模型更准，但更慢，所以只对少量候选做精排。可以用 lru_cache 把模型缓存起来，避免每次请求重新加载。
def rerank(query: str, results: list[dict], top_k: int = 3) -> list[dict]:
    pairs = [(query, item["doc"]["text"]) for item in results]
    model = CrossEncoder("BAAI/bge-reranker-base")
    scores = model.predict(pairs)
    order = np.argsort(scores)[::-1][:top_k]
    return [results[i] for i in order]


