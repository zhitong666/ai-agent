from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.llm import parse_job_description
from app.models import JobDescription

from app.agent import analyze_job, answer_question
from app.models import JobAnalysis, ChatResponse


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


