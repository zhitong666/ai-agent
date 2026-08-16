from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.models import JobDescription

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

    # Day 2 暂时返回固定数据，Day 3 会接入真实 LLM。
    return JobDescription(
        company="示例公司",
        title="AI Agent 工程师",
        seniority="mid",
        responsibilities=["设计 Agent 架构", "开发工具调用链路"],
        requirements=["Python", "FastAPI", "LLM"],
        keywords=["Agent", "LLM", "RAG"],
        domain="AI 应用",
    )
