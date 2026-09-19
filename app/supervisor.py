import os
from collections.abc import Callable, Iterator

from app.agent import get_retriever
from app.function_calling import call_required_function
from app.llm import client
from app.model_registry import get_model_name
from app.models import (
    HandoffDecision,
    SupervisorDecision,
    SupervisorResult,
    WorkerResult,
)
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


def get_max_handoffs() -> int:
    raw = os.getenv("MAX_HANDOFFS", "3")

    try:
        value = int(raw)
    except ValueError:
        return 3

    return max(1, min(value, 10))


def decision_from_handoff(
    previous_decision: SupervisorDecision,
    worker_result: WorkerResult,
    handoff: HandoffDecision,
) -> SupervisorDecision:
    context_parts = [
        previous_decision.context,
        worker_result.error or worker_result.answer,
        handoff.context,
    ]

    context = "\n\n".join(part for part in context_parts if part)

    return SupervisorDecision(
        worker=handoff.target_worker,
        goal=handoff.goal.strip() or previous_decision.goal,
        context=context,
        reason=handoff.reason,
    )


def run_supervisor(
    question: str,
    worker_registry: WorkerRegistry | None = None,
    retriever=None,
    approve_tool_call: Callable[[str, dict], bool] | None = None,
    max_handoffs: int | None = None,
) -> SupervisorResult:
    worker_registry = worker_registry or build_default_worker_registry()
    retriever = retriever or get_retriever()
    max_handoffs = max_handoffs or get_max_handoffs()

    decision = decide_worker(question, worker_registry)
    current_decision = decision
    handoffs: list[HandoffDecision] = []

    for _ in range(max_handoffs + 1):
        error = validate_decision(current_decision, worker_registry)

        if error:
            return SupervisorResult(
                decision=decision,
                worker_result=WorkerResult(
                    worker=current_decision.worker,
                    status="failed",
                    error=error,
                ),
                answer="",
                status="failed",
                handoffs=handoffs,
            )

        worker = worker_registry.get_worker(current_decision.worker)

        if worker is None:
            return SupervisorResult(
                decision=decision,
                worker_result=WorkerResult(
                    worker=current_decision.worker,
                    status="failed",
                    error=f"未知 Worker: {current_decision.worker}",
                ),
                answer="",
                status="failed",
                handoffs=handoffs,
            )

        worker_result = worker.run(
            current_decision,
            retriever,
            approve_tool_call,
        )

        if worker_result.status == "handoff" and worker_result.handoff is not None:
            handoff = worker_result.handoff
            handoffs.append(handoff)
            current_decision = decision_from_handoff(
                current_decision,
                worker_result,
                handoff,
            )
            continue

        return SupervisorResult(
            decision=decision,
            worker_result=worker_result,
            answer=worker_result.answer,
            status=(
                "completed"
                if worker_result.status == "completed"
                else "failed"
            ),
            handoffs=handoffs,
        )

    return SupervisorResult(
        decision=decision,
        worker_result=WorkerResult(
            worker=current_decision.worker,
            status="failed",
            error="超过最大 Handoff 次数",
        ),
        answer="",
        status="failed",
        handoffs=handoffs,
    )


def stream_supervisor(
    question: str,
    worker_registry: WorkerRegistry | None = None,
    retriever=None,
    approve_tool_call: Callable[[str, dict], bool] | None = None,
    max_handoffs: int | None = None,
) -> Iterator[str]:
    worker_registry = worker_registry or build_default_worker_registry()
    retriever = retriever or get_retriever()
    max_handoffs = max_handoffs or get_max_handoffs()

    try:
        decision = decide_worker(question, worker_registry)
    except Exception as exc:
        yield sse_event("error", f"Supervisor 决策失败：{exc}")
        yield sse_event("done", "")
        return

    current_decision = decision
    handoffs: list[HandoffDecision] = []

    yield sse_event("decision", current_decision.model_dump_json())

    for _ in range(max_handoffs + 1):
        worker = worker_registry.get_worker(current_decision.worker)

        if worker is None:
            yield sse_event("error", f"未知 Worker: {current_decision.worker}")
            yield sse_event("done", "")
            return

        try:
            worker_result = worker.run(
                current_decision,
                retriever,
                approve_tool_call,
            )
        except Exception as exc:
            worker_result = WorkerResult(
                worker=current_decision.worker,
                status="failed",
                error=str(exc),
            )

        yield sse_event("worker", worker_result.model_dump_json())

        if worker_result.status == "handoff" and worker_result.handoff is not None:
            handoff = worker_result.handoff
            handoffs.append(handoff)

            yield sse_event("handoff", handoff.model_dump_json())

            current_decision = decision_from_handoff(
                current_decision,
                worker_result,
                handoff,
            )

            yield sse_event("decision", current_decision.model_dump_json())
            continue

        if worker_result.status == "completed":
            yield sse_event("answer", worker_result.answer)
        else:
            yield sse_event("error", worker_result.error or "Worker 执行失败")

        yield sse_event("done", "")
        return

    yield sse_event("error", "超过最大 Handoff 次数")
    yield sse_event("done", "")