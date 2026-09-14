import hashlib
import re
from functools import lru_cache

import tiktoken

CHUNKING_VERSION = "v2"

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？!?；;])\s*")
_BLANK_LINE_RE = re.compile(r"\n\s*\n")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


@lru_cache(maxsize=1)
def _get_encoding():
    return tiktoken.get_encoding("cl100k_base")


def estimate_token_count(text: str) -> int:
    return len(_get_encoding().encode(text))


# 是内容指纹。以后知识库内容变了，chunk 文本变化，hash 也会变化，这为后续做增量更新和失效判断打基础
def content_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def chunk_text_fixed(text: str, chunk_size: int = 80, overlap: int = 16) -> list[str]:
    if overlap >= chunk_size:
        raise ValueError("overlap 必须小于 chunk_size")

    if not text:
        return []

    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = end - overlap
    return chunks


def _split_semantic_segments(text: str) -> list[str]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    segments = []

    for block in _BLANK_LINE_RE.split(text):
        block = block.strip()
        if not block:
            continue

        for sentence in _SENTENCE_SPLIT_RE.split(block):
            sentence = sentence.strip()
            if sentence:
                segments.append(sentence)

    return segments


def _detect_section(text: str) -> str:
    match = _HEADING_RE.search(text)
    return match.group(2).strip() if match else ""


# 不是无脑按字符切，而是先按空行和句号、感叹号、问号、分号等切出语义片段，再把短片段尽量合并。只有单个句子仍然太长时，才退回原来的固定切块
def chunk_text_semantic(
    text: str,
    max_chars: int = 80,
    overlap_chars: int = 16,
) -> list[str]:
    if overlap_chars >= max_chars:
        raise ValueError("overlap_chars 必须小于 max_chars")

    segments = _split_semantic_segments(text)
    if not segments:
        return []

    chunks = []
    current = ""

    for segment in segments:
        if len(segment) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(chunk_text_fixed(segment, max_chars, overlap_chars))
            continue
        
        candidate = current + segment if current else segment
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = segment

    if current: 
        chunks.append(current)

    return chunks
    

def chunk_text_by_paragraph(
    text: str,
    max_chars: int = 80,
    overlap_chars: int = 16,
) -> list[str]:
    chunks = []

    for paragraph in text.splitlines():
        paragraph = paragraph.strip()
        if not paragraph:
            continue
    
        if len(paragraph) <= max_chars:
            chunks.append(paragraph)
            continue

        pieces = chunk_text_semantic(paragraph, max_chars, overlap_chars)
        if not pieces:
            pieces = chunk_text_fixed(paragraph, max_chars, overlap_chars)
        chunks.extend(pieces)

    return chunks


def chunk_documents(
    documents,
    strategy="semantic",
    chunk_size=80,
    overlap=16,
):
    chunks = []

    for doc in documents:
        doc_id = str(doc.get("id", "unknown"))
        title = doc.get("title", "")
        source_uri = doc.get("source_uri", "")
        source_type = doc.get("source_type", "unknown")
        language = doc.get("language", "zh")
        doc_section = doc.get("section", "")
        text = doc.get("text", "")

        if strategy == "paragraph":
            pieces = chunk_text_by_paragraph(text, chunk_size, overlap)
        elif strategy == "semantic":
            pieces = chunk_text_semantic(text, chunk_size, overlap)
        else:
            pieces = chunk_text_fixed(text, chunk_size, overlap)

        doc_chunks = []
        for index, piece in enumerate(pieces):
            doc_chunks.append(
                {
                    "chunk_id": f"{doc_id}-{index}",
                    "doc_id": doc_id,
                    "title": title,
                    "text": piece,
                    "chunk_index": index,
                    "source_uri": source_uri,
                    "source_type": source_type,
                    "section": doc_section or _detect_section(piece),
                    "language": language,
                    "char_count": len(piece),
                    "token_count": estimate_token_count(piece), # 使用 tiktoken 估算
                    "content_hash": content_hash(piece),
                    "chunking_version": CHUNKING_VERSION,
                    "prev_chunk_id": None,
                    "next_chunk_id": None,
                }
            )

        for index, chunk in enumerate(doc_chunks):
            chunk["prev_chunk_id"] = (
                doc_chunks[index - 1]["chunk_id"] if index > 0 else None
            )
            chunk["next_chunk_id"] = (
                doc_chunks[index + 1]["chunk_id"]
                if index < len(doc_chunks) - 1
                else None
            )

        chunks.extend(doc_chunks)

    return chunks