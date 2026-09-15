import os
from collections.abc import Callable, Iterator

from app.agent import get_retriever
from app.function_calling import call_required_function
from app.llm import client
from app.model_registry import get_model_name
from app.models import SupervisorDecision, SupervisorResult, WorkerResult
from app.prompts import build_supervisor_messages
from app.streaming import sse_event
from app.structured_output import build_tool_parameters_from_model
from app.workers import WorkerRegistry, build_default_worker_registry


SUPERVISOR_DECISION_TOOL = {
    "type": "function",
    "function": {
        "name": "save_supervisor_decision",
        "description": "保存 Supervisor 的路由决策",
        "parameters": build_tool_parameters_from_model(SupervisorDecision),
    },
}


def decide_worker(
    question: str,
    worker_registry: WorkerRegistry,
    *,
    model_name: str | None = None,
    max_attempts: int = 3,
) -> SupervisorDecision:
    messages = build_supervisor_messages(
        question,
        worker_registry.catalog_text(),
    )

    return call_required_function(
        client=client,
        messages=messages,
        tools=[SUPERVISOR_DECISION_TOOL],
        tool_name="save_supervisor_decision",
        output_model=SupervisorDecision,
        model_name=model_name or get_model_name(
            "supervisor",
            os.getenv("OPENAI_MODEL"),
        ),
        max_attempts=max_attempts,
    )


def validate_decision(
    decision: SupervisorDecision,
    worker_registry: WorkerRegistry,
) -> str | None:
    if not decision.goal.strip():
        return "Supervisor 决策缺少 goal"

    if decision.worker not in worker_registry.worker_names():
        return f"未知 Worker: {decision.worker}"

    return None


def run_supervisor(
    question: str,
    worker_registry: WorkerRegistry | None = None,
    retriever=None,
    approve_tool_call: Callable[[str, dict], bool] | None = None,
) -> SupervisorResult:
    worker_registry = worker_registry or build_default_worker_registry()
    retriever = retriever or get_retriever()

    decision = decide_worker(question, worker_registry)

    error = validate_decision(decision, worker_registry)

    if error:
        return SupervisorResult(
            decision=decision,
            worker_result=WorkerResult(
                worker=decision.worker,
                status="failed",
                error=error,
            ),
            answer="",
            status="failed",
        )

    worker = worker_registry.get_worker(decision.worker)

    if worker is None:
        return SupervisorResult(
            decision=decision,
            worker_result=WorkerResult(
                worker=decision.worker,
                status="failed",
                error=f"未知 Worker: {decision.worker}",
            ),
            answer="",
            status="failed",
        )

    worker_result = worker.run(
        decision,
        retriever,
        approve_tool_call,
    )

    return SupervisorResult(
        decision=decision,
        worker_result=worker_result,
        answer=worker_result.answer,
        status="completed" if worker_result.status == "completed" else "failed",
    )


def stream_supervisor(
    question: str,
    worker_registry: WorkerRegistry | None = None,
    retriever=None,
    approve_tool_call: Callable[[str, dict], bool] | None = None,
) -> Iterator[str]:
    worker_registry = worker_registry or build_default_worker_registry()
    retriever = retriever or get_retriever()

    try:
        decision = decide_worker(question, worker_registry)
    except Exception as exc:
        yield sse_event("error", f"Supervisor 决策失败：{exc}")
        yield sse_event("done", "")
        return

    yield sse_event("decision", decision.model_dump_json())

    worker = worker_registry.get_worker(decision.worker)

    if worker is None:
        yield sse_event(
            "error",
            f"未知 Worker: {decision.worker}",
        )
        yield sse_event("done", "")
        return

    try:
        worker_result = worker.run(
            decision,
            retriever,
            approve_tool_call,
        )
    except Exception as exc:
        worker_result = WorkerResult(
            worker=decision.worker,
            status="failed",
            error=str(exc),
        )

    yield sse_event("worker", worker_result.model_dump_json())

    if worker_result.status == "completed":
        yield sse_event("answer", worker_result.answer)
    else:
        yield sse_event("error", worker_result.error or "Worker 执行失败")

    yield sse_event("done", "")