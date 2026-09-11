from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import uuid

from app.llm import parse_job_description
from app.models import JobDescription
from app.agent import analyze_job, answer_question, stream_answer_question
from app.models import JobAnalysis, ChatResponse
from app.approval import approval_store
from app.react import stream_react_loop
from app.observability import observability_store, trace_stream


app = FastAPI(title="AI Job Agent", version="0.1.0")

class ParseRequest(BaseModel):
    text: str = Field(min_length=1)

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

@app.post("/jd/parse", response_model=JobDescription)
def parse_jd(request: ParseRequest) -> JobDescription:
    if not request.text.strip():
        raise HTTPException(status_code=422, detail="text must not be empty")

    return parse_job_description(request.text)


class AnalyzeRequest(BaseModel):
    text: str = Field(min_length=1)

@app.post("/jd/analyze", response_model=JobAnalysis)
def analyze_jd(request: AnalyzeRequest) -> JobAnalysis:
    if not request.text.strip():
        raise HTTPException(status_code=422, detail="text must not be empty")
    
    return analyze_job(request.text)


class ChatRequest(BaseModel):
    session_id: str
    question: str = Field(min_length=1)

@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    return answer_question(request.session_id, request.question)

@app.post("/chat/stream")
def chat_stream(request: ChatRequest):
    if not request.question.strip():
        raise HTTPException(status_code=422, detail="question must not be empty")

    # StreamingResponse 接收一个生成器，边生成边返回
    return StreamingResponse(
        stream_answer_question(request.session_id, request.question),
        media_type="text/event-stream" # 告诉浏览器这是 SSE 流
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
        media_type="text/event-stream"
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

    