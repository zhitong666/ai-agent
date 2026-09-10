from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app import agent, streaming
from app.main import app
from app.memory import SessionStore


client = TestClient(app)


class FakeRetriever:
    def retrieve(self, query, top_k=3):
        return [
            {
                "doc": {
                    "chunk_id": "doc-rag-0",
                    "title": "RAG",
                    "text": "RAG 是检索增强生成。",
                },
                "score": 0.9,
            }
        ]


def make_stream_chunk(content):
    delta = MagicMock()
    delta.content = content

    choice = MagicMock()
    choice.delta = delta

    chunk = MagicMock()
    chunk.choices = [choice]
    return chunk


def test_stream_answer_question_yields_chunks_then_done():
    store = SessionStore()

    chunks = [
        make_stream_chunk("RAG"),
        make_stream_chunk(" 是"),
        make_stream_chunk("检索增强生成。"),
        make_stream_chunk(None),
    ]

    with patch("app.agent.session_store", store), patch.object(
        agent.client.chat.completions,
        "create",
        return_value=chunks,
    ) as mock_create:
        events = list(
            agent.stream_answer_question(
                "s1",
                "什么是 RAG",
                retriever=FakeRetriever(),
            )
        )

    assert events == [
        streaming.sse_event("chunk", "RAG"),
        streaming.sse_event("chunk", " 是"),
        streaming.sse_event("chunk", "检索增强生成。"),
        streaming.sse_event("done", ""),
    ]

    assert store.get("s1").get_messages() == [
        {"role": "user", "content": "什么是 RAG"},
        {"role": "assistant", "content": "RAG 是检索增强生成。"},
    ]

    assert mock_create.call_args.kwargs["stream"] is True


def test_chat_stream_endpoint_returns_sse():
    def fake_stream(session_id, question):
        yield streaming.sse_event("chunk", "你好")
        yield streaming.sse_event("done", "")

    with patch("app.main.stream_answer_question", side_effect=fake_stream):
        response = client.post(
            "/chat/stream",
            json={"session_id": "s1", "question": "你好"},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: chunk" in response.text
    assert "data: 你好" in response.text
    assert "event: done" in response.text


def test_chat_stream_rejects_empty_question():
    response = client.post(
        "/chat/stream",
        json={"session_id": "s1", "question": ""},
    )

    assert response.status_code == 422