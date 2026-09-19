from typing import Any, Literal

from pydantic import BaseModel, Field


class JobDescription(BaseModel):
    company: str = Field(..., min_length=1, description="公司名称")
    title: str = Field(..., min_length=1, description="岗位名称")
    seniority: Literal["junior", "mid", "senior", "staff", "unknown"] = Field(
        "unknown",
        description="岗位级别",
    )
    responsibilities: list[str] = Field(default_factory=list, description="岗位职责")
    requirements: list[str] = Field(default_factory=list, description="技能要求")
    keywords: list[str] = Field(default_factory=list, description="检索关键词")
    domain: str = Field("", description="业务领域")

class JobAnalysis(BaseModel):
    summary: str = Field(..., min_length=1, description="岗位总体概述")
    matched_skills: list[str] = Field(default_factory=list, description="当前已具备技能")
    missing_skills: list[str] = Field(default_factory=list, description="还缺少的技能")
    interview_questions: list[str] = Field(default_factory=list, description="可能出现的面试题")
    study_plan: list[str] = Field(default_factory=list, description="学习计划建议")
    


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


# 记录一步行动、输入和观察结果
class ReactStep(BaseModel):
    action: str
    action_input: str = ""
    observation: str = ""


# 最终答案和中间轨迹，后面可观测性会继续用到
class ReactResult(BaseModel):
    answer: str
    steps: list[ReactStep] = Field(default_factory=list)


# 生产含义：PlanStep 是模型输出，PlanStepState 是运行状态。不要把运行状态和模型输出混在一个模型里，否则工具 Schema 会污染，也容易让模型伪造 status。
class PlanStep(BaseModel):
    id: str = Field(..., min_length=1, description="步骤 ID，例如 step-1")
    goal: str = Field(..., min_length=1, description="这一步要完成什么")
    tool: str = Field(..., min_length=1, description="要调用的工具名")
    input: str = Field(
        "",
        description=(
            "工具输入；当 tool=search_knowledge 时必填，"
            "list_knowledge_titles 时留空"
        ),
    )
    depends_on: list[str] = Field(default_factory=list, description="依赖步骤 ID")

class Plan(BaseModel):
    goal: str = Field(..., min_length=1, description="整体目标")
    steps: list[PlanStep] = Field(default_factory=list, description="步骤列表")

class PlanStepState(PlanStep):
    status: Literal["pending", "running", "completed", "failed", "skipped"] = "pending"
    observation: str = ""

class PlanExecutionResult(BaseModel):
    plan: Plan
    steps: list[PlanStepState] = Field(default_factory=list)
    answer: str = ""
    error: str = ""
    status: Literal["completed", "failed", "stopped"] = "completed"


class SupervisorDecision(BaseModel):
    worker: str = Field(..., min_length=1, description="要交给哪个 Worker")
    goal: str = Field(..., min_length=1, description="交给 Worker 的具体目标")
    context: str = Field("", description="Worker 需要的原始上下文，例如 JD 文本")
    reason: str = Field("", description="为什么这样路由，便于审计")


class HandoffDecision(BaseModel):
    target_worker: str = Field(..., min_length=1, description="交接给哪个 Worker")
    goal: str = Field("", description="交接后的目标")
    context: str = Field("", description="交接给下一个 Worker 的补充上下文")
    reason: str = Field("", description="为什么要交接")


class WorkerResult(BaseModel):
    worker: str
    status: Literal["completed", "failed", "handoff"] = "completed"
    answer: str = ""
    error: str = ""
    handoff: HandoffDecision | None = None


class SupervisorResult(BaseModel):
    decision: SupervisorDecision
    worker_result: WorkerResult
    answer: str = ""
    status: Literal["completed", "failed"] = "completed"
    handoffs: list[HandoffDecision] = Field(default_factory=list)


class GraphRunStatus(BaseModel):
    run_id: str
    request_id: str | None = None # 用于幂等
    tenant_id: str = "default" # 用于隔离
    status: Literal["running", "completed", "failed", "interrupted"] = "running"
    state: dict = Field(default_factory=dict)
    next_nodes: list[str] = Field(default_factory=list)
    result: SupervisorResult | None = None
    error: str = ""


class MemoryRecord(BaseModel):
    memory_id: str
    namespace: str
    key: str
    value: Any
    created_at: str
    updated_at: str