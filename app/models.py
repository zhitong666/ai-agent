from typing import Literal

from pydantic import BaseModel, Field

class JobDescription(BaseModel): 
    company: str
    title: str
    seniority: Literal["junior", "mid", "senior", "staff", "unknown"] = "unknown"
    responsibilities: list[str] = Field(default_factory=list)
    requirements: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    domain: str = ""

class JobAnalysis(BaseModel):
    summary: str # 岗位概述
    matched_skills: list[str] = Field(default_factory=list) # 当前可能已经具备的技能
    missing_skills: list[str] = Field(default_factory=list) # 还缺少的技能
    interview_questions: list[str] = Field(default_factory=list) # 可能出现的面试题
    study_plan: list[str] = Field(default_factory=list) # 学习计划建议
    


# Source 表示一条引用来源
class Source(BaseModel):
    chunk_id: str
    title: str
    text: str
    score: float


# ChatResponse.sources 默认是空列表，向后兼容没有来源的情况
class ChatResponse(BaseModel):
    reply: str
    sources: list[Source] = Field(default_factory=list)