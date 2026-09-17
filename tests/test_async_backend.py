import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from openai import APITimeoutError

from app import async_llm
from app.main import app


def make_completion(content):
    message = MagicMock()
    message.content = content

    choice = MagicMock()
    choice.message = message

    response = MagicMock()
    response.choices = [choice]
    return response


def test_async_retry_uses_awaitable_sleep_and_recovers():
    async def scenario():
        client = MagicMock()
        client.chat.completions.create = AsyncMock(
            side_effect=[APITimeoutError("timeout"), make_completion("ok")]
        )

        with patch("app.async_llm.asyncio.sleep", new=AsyncMock()) as sleep:
            response = await async_llm.chat_completion_with_retry_async(
                client,
                model="deepseek-chat",
                messages=[{"role": "user", "content": "hi"}],
                max_retries=2,
            )

        assert response.choices[0].message.content == "ok"
        assert sleep.await_count == 1
        assert client.chat.completions.create.await_count == 2

    asyncio.run(scenario())


def test_async_chat_endpoint_returns_patched_response():
    async def scenario():
        async def fake_answer_async(
            client,
            session_id,
            question,
            retriever=None,
            semaphore=None,
            session_store=None,
        ):
            return {"reply": "async ok", "sources": []}

        app.state.async_client = MagicMock()
        app.state.llm_semaphore = asyncio.Semaphore()
        app.state.session_store = MagicMock()

        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            with patch(
                "app.main.answer_question_async",
                side_effect=fake_answer_async,
            ):
                response = await client.post(
                    "/chat",
                    json={"session_id": "s1", "question": "hello"},
                )

        assert response.status_code == 200
        assert response.json()["reply"] == "async ok"

    asyncio.run(scenario())


def test_async_chat_requests_overlap():
    async def scenario():
        active = 0
        peak = 0
        lock = asyncio.Lock()
        release = asyncio.Event()
        all_started = asyncio.Event()

        async def slow_answer(
            client,
            session_id,
            question,
            retriever=None,
            semaphore=None,
            session_store=None,
        ):
            nonlocal active, peak

            async with lock:
                active += 1
                peak = max(peak, active)
                if active == 3:
                    all_started.set()

            await release.wait()

            async with lock:
                active -= 1

            return {"reply": "ok", "sources": []}

        app.state.async_client = MagicMock()
        app.state.llm_semaphore = asyncio.Semaphore()
        app.state.session_store = MagicMock()

        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            with patch("app.main.answer_question_async", side_effect=slow_answer):
                tasks = [
                    asyncio.create_task(
                        client.post(
                            "/chat",
                            json={"session_id": f"s{i}", "question": "q"},
                        )
                    )
                    for i in range(3)
                ]

                await asyncio.wait_for(all_started.wait(), timeout=0.5)
                release.set()
                responses = await asyncio.gather(*tasks)

        assert peak >= 3
        assert all(response.status_code == 200 for response in responses)

    asyncio.run(scenario())


def test_async_chat_stream_endpoint_consumes_async_generator():
    async def scenario():
        async def fake_stream(
            client,
            session_id,
            question,
            retriever=None,
            semaphore=None,
            session_store=None,
        ):
            yield "event: chunk\ndata: 你好\n\n"
            yield "event: done\ndata: \n\n"

        app.state.async_client = MagicMock()
        app.state.llm_semaphore = asyncio.Semaphore()
        app.state.session_store = MagicMock()
        
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            with patch(
                "app.main.stream_answer_question_async",
                side_effect=fake_stream,
            ):
                response = await client.post(
                    "/chat/stream",
                    json={"session_id": "s1", "question": "hello"},
                )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert "event: chunk" in response.text
        assert "event: done" in response.text

    asyncio.run(scenario())