from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app import agent, streaming
from app.auth_security import create_access_token
from app.main import app
from app.memory import SessionStore
from app.quota import QuotaDecision


client = TestClient(app)


def auth_headers():
    token = create_access_token(
        "test-user",
        ["user"],
        "default",
    )
    return {"Authorization": f"Bearer {token}"}


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
    async def fake_stream(
        client,
        session_id,
        question,
        scene="job",
        retriever=None,
        semaphore=None,
        session_store=None,
    ):
        yield streaming.sse_event("chunk", "你好")
        yield streaming.sse_event("done", "")

    app.state.session_store = MagicMock()
    app.state.rate_limiter = MagicMock()
    app.state.rate_limiter.allow = AsyncMock(return_value=True)
    app.state.quota_service = MagicMock()
    app.state.quota_service.check_request = AsyncMock(
        return_value=QuotaDecision(allowed=True)
    )
    app.state.quota_service.consume_tokens = AsyncMock(
        return_value=QuotaDecision(allowed=True)
    )

    with patch(
        "app.main.stream_answer_question_async",
        side_effect=fake_stream,
    ):
            response = client.post(
                "/chat/stream",
                json={"session_id": "s1", "question": "你好"},
                headers=auth_headers(),
            )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: chunk" in response.text
    assert "data: 你好" in response.text
    assert "event: done" in response.text


def test_chat_stream_rejects_empty_question():
    app.state.rate_limiter = MagicMock()
    app.state.rate_limiter.allow = AsyncMock(return_value=False)
    app.state.quota_service = MagicMock()

    response = client.post(
        "/chat/stream",
        json={"session_id": "s1", "question": ""},
        headers=auth_headers(),
    )

    assert response.status_code == 422
