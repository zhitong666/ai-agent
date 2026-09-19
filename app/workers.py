from collections.abc import Callable
from dataclasses import dataclass

from app.agent import analyze_job
from app.models import HandoffDecision, SupervisorDecision, WorkerResult
from app.plan_execute import execute_plan, plan_task
from app.tools import build_default_registry

JD_MARKERS = (
    "招聘",
    "岗位职责",
    "任职要求",
    "要求掌握",
    "职位描述",
)


def _looks_like_jd(text: str) -> bool:
    normalized = text.lower()
    return any(marker in normalized for marker in JD_MARKERS)


@dataclass(frozen=True)
class WorkerSpec:
    name: str
    description: str
    run: Callable

class WorkerRegistry:
    def __init__(self):
        self._workers: dict[str, WorkerSpec] = {}

    def register(self, spec: WorkerSpec) -> None:
        if spec.name in self._workers:
            raise ValueError(f"Worker 已注册：{spec.name}")

        self._workers[spec.name] = spec

    def get_worker(self, name: str) -> WorkerSpec | None:
        return self._workers.get(name)

    def worker_names(self) -> list[str]:
        return list(self._workers)

    def catalog_text(self) -> str:
        return "\n".join(
            f"- {worker.name}: {worker.description}"
            for worker in self._workers.values()
        )


def run_knowledge_worker(
    decision: SupervisorDecision,
    retriever,
    approve_tool_call=None,
) -> WorkerResult:
    registry = build_default_registry()
    question = decision.context.strip() or decision.goal

    if _looks_like_jd(question):
        return WorkerResult(
            worker="knowledge",
            status="handoff",
            handoff=HandoffDecision(
                target_worker="jd_analysis",
                goal="解析 JD 并生成岗位分析",
                context=question,
                reason="输入包含 JD 特征，应交由 jd_analysis 处理",
            ),
        )

    try:
        plan = plan_task(question, registry)
        result = execute_plan(
            question,
            plan,
            registry,
            retriever,
            approve_tool_call,
        )
    except Exception as exc:
        return WorkerResult(
            worker="knowledge",
            status="failed",
            error=str(exc),
        )

    if result.status != "completed":
        return WorkerResult(
            worker="knowledge",
            status="failed",
            error=result.error or "知识 Worker 执行失败",
        )

    return WorkerResult(
        worker="knowledge",
        status="completed",
        answer=result.answer,
    )


def run_jd_analysis_worker(
    decision: SupervisorDecision,
    retriever,
    approve_tool_call=None,
) -> WorkerResult:
    jd_text = decision.context.strip() or decision.goal.strip()

    if not _looks_like_jd(jd_text):
        return WorkerResult(
            worker="jd_analysis",
            status="handoff",
            handoff=HandoffDecision(
                target_worker="knowledge",
                goal=decision.goal or jd_text,
                context=jd_text,
                reason="输入不是 JD 文本，应交由 knowledge 处理",
            ),
        )

    if not jd_text:
        return WorkerResult(
            worker="jd_analysis",
            status="failed",
            error="缺少 JD 文本",
        )

    try:
        analysis = analyze_job(jd_text, retriever)
    except Exception as exc:
        return WorkerResult(
            worker="jd_analysis",
            status="failed",
            error=str(exc),
        )

    return WorkerResult(
        worker="jd_analysis",
        status="completed",
        answer=analysis.model_dump_json(),
    )


def build_default_worker_registry() -> WorkerRegistry:
    registry = WorkerRegistry()

    registry.register(
        WorkerSpec(
            name="knowledge",
            description="知识库问答和学习路径咨询",
            run=run_knowledge_worker,
        )
    )

    registry.register(
        WorkerSpec(
            name="jd_analysis",
            description="解析 JD 并生成岗位分析",
            run=run_jd_analysis_worker,
        )
    )

    return registry