from app.async_agent import analyze_job_async
from app.async_llm import create_async_client, create_llm_semaphore
from app.job_store import JobStore
from app.redis_client import create_redis_client


async def on_startup(ctx):
    redis = create_redis_client()

    ctx["redis"] = redis
    ctx["job_store"] = JobStore(redis)
    ctx["async_client"] = create_async_client()
    ctx["llm_semaphore"] = create_llm_semaphore()


async def on_shutdown(ctx):
    await ctx["async_client"].close()
    await ctx["redis"].aclose()


async def analyze_job_task(ctx, jd_text: str, job_id: str):
    job_store = ctx["job_store"]

    await job_store.mark_running(job_id)

    try:
        result = await analyze_job_async(
            ctx["async_client"],
            jd_text,
            semaphore=ctx["llm_semaphore"],
        )
        payload = result.model_dump()
        await job_store.complete(job_id, payload)
        return payload
    except Exception as exc:
        await job_store.fail(job_id, str(exc))
        raise