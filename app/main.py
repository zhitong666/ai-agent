import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.agent import get_retriever
from app.approval import approval_store
from app.async_agent import (
    analyze_job_async,
    answer_question_async,
    parse_job_description_async,
    stream_answer_question_async,
)
from app.async_llm import create_async_client, create_llm_semaphore
from app.mcp_agent import stream_mcp_react_loop
from app.models import (
    ChatResponse,
    GraphRunStatus,
    JobAnalysis,
    JobDescription,
    MemoryRecord,
)
from app.observability import observability_store, trace_stream
from app.plan_execute import stream_plan_execute
from app.postgres import create_postgres_pool
from app.postgres_session_store import PostgresSessionStore
from app.react import stream_react_loop
from app.shared_memory import SharedMemoryStore
from app.supervisor import stream_supervisor
from app.supervisor_graph import (
    get_graph_run,
    resume_graph_run,
    start_graph_run,
    stream_graph_supervisor,
)
from app.tools import build_default_registry

MEMORY_DB_PATH = "data/shared_memory.sqlite"


def get_memory_store():
    return SharedMemoryStore(MEMORY_DB_PATH)


@asynccontextmanager
async def lifespan(app):
    app.state.async_client = create_async_client()
    app.state.llm_semaphore = create_llm_semaphore()
    app.state.postgres_pool = await create_postgres_pool()
    app.state.session_store = PostgresSessionStore(app.state.postgres_pool)

    try:
        yield
    finally:
        await app.state.async_client.close()
        await app.state.postgres_pool.close()


app = FastAPI(
    title="AI Job Agent",
    version="0.1.0",
    lifespan=lifespan,
)


class ParseRequest(BaseModel):
    text: str = Field(min_length=1)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/db")
async def health_db() -> dict[str, str]:
    try:
        async with app.state.postgres_pool.connection() as conn, conn.cursor() as cur:
            await cur.execute("SELECT 1")
            row = await cur.fetchone()

        if row is None:
            raise RuntimeError("database returned no result")
    except Exception as exc:
        raise HTTPException(status_code=503, detail="database unavailable") from exc

    return {"status": "ok"}


@app.post("/jd/parse", response_model=JobDescription)
async def parse_jd(request: ParseRequest) -> JobDescription:
    if not request.text.strip():
        raise HTTPException(status_code=422, detail="text must not be empty")

    return await parse_job_description_async(
        app.state.async_client,
        request.text,
        semaphore=app.state.llm_semaphore,
    )


class AnalyzeRequest(BaseModel):
    text: str = Field(min_length=1)


@app.post("/jd/analyze", response_model=JobAnalysis)
async def analyze_jd(request: AnalyzeRequest) -> JobAnalysis:
    if not request.text.strip():
        raise HTTPException(status_code=422, detail="text must not be empty")

    return await analyze_job_async(
        app.state.async_client,
        request.text,
        semaphore=app.state.llm_semaphore,
    )


class ChatRequest(BaseModel):
    session_id: str
    question: str = Field(min_length=1)


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    return await answer_question_async(
        app.state.async_client,
        request.session_id,
        request.question,
        semaphore=app.state.llm_semaphore,
        session_store=app.state.session_store,
    )


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    if not request.question.strip():
        raise HTTPException(status_code=422, detail="question must not be empty")

    return StreamingResponse(
        stream_answer_question_async(
            app.state.async_client,
            request.session_id,
            request.question,
            semaphore=app.state.llm_semaphore,
            session_store=app.state.session_store,
        ),
        media_type="text/event-stream",
    )


class AgentStreamRequest(BaseModel):
    question: str = Field(min_length=1)
    request_id: str | None = None


class ApprovalRequest(BaseModel):
    request_id: str
    approved: bool


@app.post("/agent/stream")
def agent_stream(request: AgentStreamRequest):
    if not request.question.strip():
        raise HTTPException(status_code=422, detail="question must not be empty")

    request_id = request.request_id or str(uuid.uuid4())

    def approve_tool_call(tool_name, arguments):
        return approval_store.wait(request_id)

    stream = stream_react_loop(
        request.question,
        approve_tool_call=approve_tool_call,
        approval_request_id=request_id,
    )

    return StreamingResponse(
        trace_stream(
            observability_store,
            request.question,
            request_id,
            stream,
        ),
        media_type="text/event-stream",
    )


@app.post("/agent/approve")
def agent_approve(request: ApprovalRequest):
    approval_store.decide(request.request_id, request.approved)
    return {"status": "ok"}


@app.get("/agent/traces/{trace_id}")
def get_agent_trace(trace_id: str):
    trace = observability_store.get_trace(trace_id)

    if trace is None:
        raise HTTPException(status_code=404, detail="trace not found")

    return trace.model_dump()


@app.post("/agent/plan/stream")
def agent_plan_stream(request: AgentStreamRequest):
    request_id = request.request_id or str(uuid.uuid4())
    registry = build_default_registry()
    retriever = get_retriever()

    def approve_tool_call(tool_name, arguments):
        return approval_store.wait(request_id)

    stream = stream_plan_execute(
        request.question,
        registry=registry,
        retriever=retriever,
        approve_tool_call=approve_tool_call,
    )

    return StreamingResponse(stream, media_type="text/event-stream")


@app.post("/agent/supervisor/stream")
def agent_supervisor_stream(request: AgentStreamRequest):
    if not request.question.strip():
        raise HTTPException(status_code=422, detail="question must not be empty")

    request_id = request.request_id or str(uuid.uuid4())

    def approve_tool_call(tool_name, arguments):
        return approval_store.wait(request_id)

    stream = stream_supervisor(
        request.question,
        approve_tool_call=approve_tool_call,
    )

    return StreamingResponse(stream, media_type="text/event-stream")


@app.post("/agent/graph/stream")
def agent_graph_stream(request: AgentStreamRequest):
    if not request.question.strip():
        raise HTTPException(status_code=422, detail="question must not be empty")

    request_id = request.request_id or str(uuid.uuid4())

    def approve_tool_call(tool_name, arguments):
        return approval_store.wait(request_id)

    stream = stream_graph_supervisor(
        request.question,
        approve_tool_call=approve_tool_call,
    )

    return StreamingResponse(stream, media_type="text/event-stream")


class GraphRunRequest(BaseModel):
    question: str = Field(min_length=1)
    run_id: str | None = None
    request_id: str | None = None
    tenant_id: str = "default"
    timeout_seconds: float | None = None


@app.post("/agent/graph/start", response_model=GraphRunStatus)
def agent_graph_start(request: GraphRunRequest):
    return start_graph_run(
        request.question,
        run_id=request.run_id,
        request_id=request.request_id,
        tenant_id=request.tenant_id,
        timeout_seconds=request.timeout_seconds,
        interrupt_before=["finalize"],
    )


class GraphResumeRequest(BaseModel):
    run_id: str
    tenant_id: str = "default"
    timeout_seconds: float | None = None


@app.post("/agent/graph/resume", response_model=GraphRunStatus)
def agent_graph_resume(request: GraphResumeRequest):
    return resume_graph_run(
        request.run_id,
        tenant_id=request.tenant_id,
        timeout_seconds=request.timeout_seconds,
    )


@app.get("/agent/graph/state/{run_id}", response_model=GraphRunStatus)
def agent_graph_state(
    run_id: str,
    tenant_id: str = "default",
):
    return get_graph_run(run_id, tenant_id=tenant_id)


@app.get("/agent/memory/{run_id}", response_model=list[MemoryRecord])
def agent_memory_list(
    run_id: str,
    tenant_id: str = "default",
):
    namespace = f"tenant:{tenant_id}:run:{run_id}"
    return get_memory_store().list_namespace(namespace)


@app.get("/agent/memory/{run_id}/{key}", response_model=MemoryRecord)
def agent_memory_get(
    run_id: str,
    key: str,
    tenant_id: str = "default",
):
    namespace = f"tenant:{tenant_id}:run:{run_id}"
    record = get_memory_store().get(namespace, key)

    if record is None:
        raise HTTPException(status_code=404, detail="memory record not found")

    return record


@app.delete("/agent/memory/{run_id}/{key}")
def agent_memory_delete(
    run_id: str,
    key: str,
    tenant_id: str = "default",
):
    namespace = f"tenant:{tenant_id}:run:{run_id}"
    deleted = get_memory_store().delete(namespace, key)

    if not deleted:
        raise HTTPException(status_code=404, detail="memory record not found")

    return {"status": "ok"}


@app.post("/agent/mcp/stream")
def agent_mcp_stream(request: AgentStreamRequest):
    if not request.question.strip():
        raise HTTPException(status_code=422, detail="question must not be empty")

    request_id = request.request_id or str(uuid.uuid4())

    def approve_tool_call(tool_name, arguments):
        return approval_store.wait(request_id)

    stream = stream_mcp_react_loop(
        request.question,
        approve_tool_call=approve_tool_call,
        approval_request_id=request_id,
    )

    return StreamingResponse(
        trace_stream(
            observability_store,
            request.question,
            request_id,
            stream,
        ),
        media_type="text/event-stream",
    )