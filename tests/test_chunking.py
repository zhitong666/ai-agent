# 固定切块的块数和重叠
# 重叠参数校验
# 按段落切分 chunk_documents 的元数据
# 切块后 RAGRetriever 能否正确返回最相关的 chunk

import numpy as np 
import pytest

from app.chunking import (
    chunk_documents,
    chunk_text_by_paragraph,
    chunk_text_fixed,
)
from app.rag import RAGRetriever

class FakeModel:
    def encode(self, texts, normalize_embeddings=True):
        vectors = {
            "python": [1.0, 0.0, 0.0],
            "docker": [0.0, 1.0, 0.0],
            "rag": [0.0, 0.0, 1.0],
        }
        return np.array([vectors[text] for text in texts])


# 用 chunk_size=4、overlap=2 切 0123456789，验证结果是 0123、2345、4567、6789，能看到相邻块之间有重叠
def test_chunk_text_fixed_splits_with_overlap():
    text = "0123456789"

    chunks = chunk_text_fixed(text, chunk_size=4, overlap=2)

    assert chunks == ["0123", "2345", "4567", "6789"]


# 验证 overlap >= chunk_size 时抛 ValueError
def test_chunk_text_fixed_raises_when_overlap_too_large():
    with pytest.raises(ValueError):
        chunk_text_fixed("hello", chunk_size=4, overlap=4)


# 验证按段落切分能过滤空行、去掉首尾空格，得到三个干净段落
def test_chunk_text_by_paragraph_splits_on_newlines():
    text = "第一段\n第二段\n\n第三段"

    chunks = chunk_text_by_paragraph(text)

    assert chunks == ["第一段", "第二段", "第三段"]


# 验证切块后的 chunk_id、doc_id、title、chunk_index 是否正确生成，并确认总共切出 4 块
def test_chunk_documents_adds_metadata():
    documents = [
        {"id": "doc-a", "title": "A", "text": "0123456789"},
    ]

    chunks = chunk_documents(documents, strategy="fixed", chunk_size=4, overlap=2)

    assert len(chunks) == 4
    assert chunks[0]["chunk_id"] == "doc-a-0"
    assert chunks[0]["doc_id"] == "doc-a"
    assert chunks[0]["title"] == "A"
    assert chunks[0]["chunk_index"] == 0
    assert chunks[-1]["chunk_index"] == 3


# 复用 FakeModel，把三个 chunk 传给 RAGRetriever，查询 rag 时验证返回的是 doc-a-2 这个 chunk，而不是整篇文档
# 需要注意：FakeModel.encode 依赖 text 正好是 python、docker、rag 这三个 key，所以这个测试里 chunk 的 text 要写成这三个值；如果你想测任意长文本，可以把 FakeModel 改成根据文本内容返回确定性向量。
def test_retriever_returns_relevant_chunk():
    chunks = [
        {"chunk_id": "doc-a-0", "doc_id": "doc-a", "title": "A", "text": "python", "chunk_index": 0},
        {"chunk_id": "doc-a-1", "doc_id": "doc-a", "title": "A", "text": "docker", "chunk_index": 1},
        {"chunk_id": "doc-a-2", "doc_id": "doc-a", "title": "A", "text": "rag", "chunk_index": 2},
    ]

    retriever = RAGRetriever(chunks, FakeModel())

    results = retriever.retrieve("rag", top_k=1)

    assert results[0]["doc"]["chunk_id"] == "doc-a-2"