from app.chunking import (
    chunk_documents,
    chunk_text_semantic,
    content_hash,
)


def test_semantic_chunk_keeps_short_sentence_boundaries():
    text = "第一句。第二句。第三句。"

    chunks = chunk_text_semantic(text, max_chars=4, overlap_chars=1)

    assert chunks == ["第一句。", "第二句。", "第三句。"]


def test_semantic_chunk_falls_back_for_long_unbroken_text():
    text = "A" * 20

    chunks = chunk_text_semantic(text, max_chars=5, overlap_chars=1)

    assert len(chunks) > 1
    assert all(0 < len(chunk) <= 5 for chunk in chunks)


def test_chunk_documents_carries_production_metadata():
    documents = [
        {
            "id": "doc-a",
            "title": "AI Agent",
            "text": "第一段。" * 3,
            "source_uri": "s3://kb/ai-agent.md",
            "source_type": "markdown",
            "section": "基础",
            "language": "zh",
        }
    ]

    chunks = chunk_documents(
        documents,
        strategy="semantic",
        chunk_size=4,
        overlap=1,
    )

    first = chunks[0]

    assert first["chunk_id"] == "doc-a-0"
    assert first["doc_id"] == "doc-a"
    assert first["source_uri"] == "s3://kb/ai-agent.md"
    assert first["source_type"] == "markdown"
    assert first["section"] == "基础"
    assert first["language"] == "zh"
    assert first["char_count"] == len(first["text"])
    assert first["token_count"] > 0
    assert len(first["content_hash"]) == 40
    assert first["prev_chunk_id"] is None
    assert first["next_chunk_id"] == "doc-a-1"


def test_prev_next_links_do_not_cross_documents():
    documents = [
        {"id": "doc-a", "title": "A", "text": "第一段。" * 3},
        {"id": "doc-b", "title": "B", "text": "第二段。" * 3},
    ]

    chunks = chunk_documents(
        documents,
        strategy="semantic",
        chunk_size=4,
        overlap=1,
    )

    doc_a = [chunk for chunk in chunks if chunk["doc_id"] == "doc-a"]
    doc_b = [chunk for chunk in chunks if chunk["doc_id"] == "doc-b"]

    assert doc_a[-1]["next_chunk_id"] is None
    assert doc_b[0]["prev_chunk_id"] is None


def test_content_hash_is_stable_and_changes_with_content():
    assert content_hash("abc") == content_hash("abc")
    assert content_hash("abc") != content_hash("abd")