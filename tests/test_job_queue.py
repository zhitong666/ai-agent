import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

from app.job_store import JobStore
from app.tasks import analyze_job_task


def test_job_store_create_and_get():
    async def scenario():
        redis = AsyncMock()
        redis.hset = AsyncMock()
        redis.hgetall = AsyncMock(
            return_value={
                "status": "queued",
                "type": "analyze_job",
                "payload": json.dumps({"text": "JD"}),
                "result": "",
                "error": "",
                "created_at": "2026-09-17T00:00:00+00:00",
                "updated_at": "2026-09-17T00:00:00+00:00",
            }
        )

        store = JobStore(redis)
        await store.create("job-1", "analyze_job", {"text": "JD"})
        job = await store.get("job-1")

        assert job["job_id"] == "job-1"
        assert job["status"] == "queued"
        assert job["payload"] == {"text": "JD"}

    asyncio.run(scenario())


def test_job_store_complete_saves_result():
    async def scenario():
        redis = AsyncMock()
        store = JobStore(redis)

        await store.complete(
            "job-1",
            {"summary": "ok"},
        )

        fields = redis.hset.await_args.kwargs["mapping"]
        assert fields["status"] == "completed"
        assert json.loads(fields["result"]) == {"summary": "ok"}

    asyncio.run(scenario())


def test_analyze_job_task_marks_completed():
    async def scenario():
        job_store = AsyncMock()
        async_client = MagicMock()
        semaphore = MagicMock()

        fake_result = MagicMock()
        fake_result.model_dump.return_value = {
            "summary": "AI Agent 工程师",
        }

        ctx = {
            "job_store": job_store,
            "async_client": async_client,
            "llm_semaphore": semaphore,
        }

        with patch_job_analysis(fake_result):
            await analyze_job_task(ctx, "某 JD", "job-1")

        assert job_store.mark_running.await_count == 1
        assert job_store.complete.await_count == 1
        assert job_store.fail.await_count == 0

    asyncio.run(scenario())


def test_analyze_job_task_marks_failed_on_error():
    async def scenario():
        job_store = AsyncMock()
        async_client = MagicMock()
        semaphore = MagicMock()

        ctx = {
            "job_store": job_store,
            "async_client": async_client,
            "llm_semaphore": semaphore,
        }

        with patch_job_analysis_error():
            try:
                await analyze_job_task(ctx, "某 JD", "job-2")
            except RuntimeError:
                pass

        assert job_store.fail.await_count == 1
        assert job_store.complete.await_count == 0

    asyncio.run(scenario())


def test_queue_integration_requires_redis():
    import os

    from app.queue import create_queue

    url = os.getenv("TEST_REDIS_URL")

    if not url:
        return

    async def scenario():
        queue = await create_queue()
        await queue.ping()
        await queue.aclose()

    asyncio.run(scenario())


def patch_job_analysis(result):
    from unittest.mock import patch

    return patch(
        "app.tasks.analyze_job_async",
        new=AsyncMock(return_value=result),
    )


def patch_job_analysis_error():
    from unittest.mock import patch

    return patch(
        "app.tasks.analyze_job_async",
        side_effect=RuntimeError("llm failed"),
    )