import json 
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

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

# 读取文档，加载Embedding模型，创建检索器
def build_retriever(path: Path) -> RAGRetriever:
    documents = load_documents(path)
    model = SentenceTransformer(DEFAULT_EMBEDDING_MODEL)
    return RAGRetriever(documents, model)