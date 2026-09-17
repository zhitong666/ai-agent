import asyncio
import os
from collections.abc import AsyncIterator

from app.agent import ANALYSIS_TOOL, build_sources, format_context, get_retriever
from app.async_function_calling import call_required_function_async
from app.async_llm import chat_completion_with_retry_async
from app.context import ContextBudget
from app.llm import SAVE_JOB_DESCRIPTION_TOOL
from app.memory import session_store as in_memory_session_store
from app.model_registry import get_model_name
from app.models import ChatResponse, JobAnalysis, JobDescription
from app.prompts import (
    build_analysis_messages,
    build_chat_messages,
    build_jd_parse_messages,
)
from app.streaming import sse_event


async def _retrieve(retriever, query: str, top_k: int = 3):
    return await asyncio.to_thread(
        retriever.retrieve,
        query,
        top_k=top_k,
    )


async def _load_history(session_store, session_id: str) -> list[dict]:
    if session_store is None:
        memory = in_memory_session_store.get(session_id)
        return memory.get_messages()

    return await session_store.get_messages(session_id)


async def _save_turn(
    session_store,
    session_id: str,
    question: str,
    answer: str,
) -> None:
    if session_store is None:
        memory = in_memory_session_store.get(session_id)
        memory.add("user", question)
        memory.add("assistant", answer)
        return

    await session_store.append_turn(session_id, question, answer)


async def parse_job_description_async(
    client,
    jd_text: str,
    semaphore=None,
) -> JobDescription:
    return await call_required_function_async(
        client,
        build_jd_parse_messages(jd_text),
        [SAVE_JOB_DESCRIPTION_TOOL],
        "save_job_description",
        JobDescription,
        model_name=get_model_name("jd_parse", os.getenv("OPENAI_MODEL")),
        max_attempts=3,
        semaphore=semaphore,
    )


async def generate_analysis_async(
    client,
    job: JobDescription,
    context: str,
    semaphore=None,
) -> JobAnalysis:
    return await call_required_function_async(
        client,
        build_analysis_messages(job, context, cot=True),
        [ANALYSIS_TOOL],
        "save_job_analysis",
        JobAnalysis,
        model_name=get_model_name("job_analysis", os.getenv("OPENAI_MODEL")),
        max_attempts=3,
        semaphore=semaphore,
    )


async def analyze_job_async(
    client,
    jd_text: str,
    retriever=None,
    semaphore=None,
) -> JobAnalysis:
    job = await parse_job_description_async(
        client,
        jd_text,
        semaphore=semaphore,
    )

    retriever = retriever or get_retriever()
    query = " ".join(job.keywords) if job.keywords else job.title

    results = await _retrieve(retriever, query)
    context = format_context(results)

    return await generate_analysis_async(
        client,
        job,
        context,
        semaphore=semaphore,
    )


async def answer_question_async(
    client,
    session_id: str,
    question: str,
    retriever=None,
    semaphore=None,
    session_store=None,
) -> ChatResponse:
    history = await _load_history(session_store, session_id)
    retriever = retriever or get_retriever()

    results = await _retrieve(retriever, question, top_k=3)
    sources = build_sources(results)
    context = format_context(results)

    messages = build_chat_messages(history, context, question)
    messages = ContextBudget().fit_messages(messages)

    response = await chat_completion_with_retry_async(
        client,
        model=get_model_name("chat", os.getenv("OPENAI_MODEL")),
        messages=messages,
        max_retries=3,
        timeout=10,
        semaphore=semaphore,
    )

    reply = response.choices[0].message.content

    await _save_turn(session_store, session_id, question, reply)

    return ChatResponse(reply=reply, sources=sources)


async def stream_answer_question_async(
    client,
    session_id: str,
    question: str,
    retriever=None,
    semaphore=None,
    session_store=None,
) -> AsyncIterator[str]:
    history = await _load_history(session_store, session_id)
    retriever = retriever or get_retriever()

    results = await _retrieve(retriever, question, top_k=3)
    context = format_context(results)

    messages = build_chat_messages(history, context, question)
    messages = ContextBudget().fit_messages(messages)

    response = await chat_completion_with_retry_async(
        client,
        model=get_model_name("chat", os.getenv("OPENAI_MODEL")),
        messages=messages,
        max_retries=3,
        timeout=10,
        stream=True,
        semaphore=semaphore,
    )

    reply_parts = []

    async for chunk in response:
        delta = chunk.choices[0].delta.content

        if delta:
            reply_parts.append(delta)
            yield sse_event("chunk", delta)

    reply = "".join(reply_parts)

    await _save_turn(session_store, session_id, question, reply)

    yield sse_event("done", "")