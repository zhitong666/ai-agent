from functools import partial
from typing import Iterator, TypedDict

from langgraph.graph import END, StateGraph

from app.agent import get_retriever
from app.models import (
    HandoffDecision,
    SupervisorDecision,
    SupervisorResult,
    WorkerResult,
)
from app.streaming import sse_event
from app.supervisor import (
    decide_worker,
    decision_from_handoff,
    get_max_handoffs,
)
from app.workers import WorkerRegistry, build_default_worker_registry


class SupervisorGraphState(TypedDict, total=False):
    question: str
    current_decision: dict
    worker_result: dict
    handoffs: list[dict]
    handoff_count: int
    result: dict


def supervisor_node(state: SupervisorGraphState, worker_registry: WorkerRegistry) -> dict:
    decision = decide_worker(state["question"], worker_registry)

    return {
        "current_decision": decision.model_dump(),
        "handoff_count": state.get("handoff_count", 0),
    }


def worker_node(
    state: SupervisorGraphState,
    worker_registry: WorkerRegistry,
    retriever,
    approve_tool_call,
) -> dict:
    decision = SupervisorDecision.model_validate(state["current_decision"])
    worker = worker_registry.get_worker(decision.worker)

    if worker is None:
        worker_result = WorkerResult(
            worker=decision.worker,
            status="failed",
            error=f"未知 Worker: {decision.worker}",
        )
    else:
        worker_result = worker.run(
            decision,
            retriever,
            approve_tool_call,
        )

    return {"worker_result": worker_result.model_dump()}


def handoff_node(state: SupervisorGraphState) -> dict:
    previous_decision = SupervisorDecision.model_validate(
        state["current_decision"]
    )
    worker_result = WorkerResult.model_validate(state["worker_result"])
    handoff = HandoffDecision.model_validate(worker_result.handoff)

    next_decision = decision_from_handoff(
        previous_decision,
        worker_result,
        handoff,
    )

    handoffs = [
        *state.get("handoffs", []),
        handoff.model_dump(),
    ]

    return {
        "current_decision": next_decision.model_dump(),
        "handoffs": handoffs,
        "handoff_count": state.get("handoff_count", 0) + 1,
    }


def finalize_node(state: SupervisorGraphState) -> dict:
    decision = SupervisorDecision.model_validate(state["current_decision"])
    worker_result = WorkerResult.model_validate(state["worker_result"])
    handoffs = [
        HandoffDecision.model_validate(item)
        for item in state.get("handoffs", [])
    ]

    if worker_result.status == "completed":
        result = SupervisorResult(
            decision=decision,
            worker_result=worker_result,
            answer=worker_result.answer,
            status="completed",
            handoffs=handoffs,
        )
    elif worker_result.status == "handoff":
        failed_worker_result = WorkerResult(
            worker=worker_result.worker,
            status="failed",
            error="超过最大 Handoff 次数",
        )

        result = SupervisorResult(
            decision=decision,
            worker_result=failed_worker_result,
            answer="",
            status="failed",
            handoffs=handoffs,
        )
    else:
        result = SupervisorResult(
            decision=decision,
            worker_result=worker_result,
            answer="",
            status="failed",
            handoffs=handoffs,
        )

    return {"result": result.model_dump()}


def build_should_handoff(max_handoffs: int):
    def should_handoff(state: SupervisorGraphState) -> str:
        worker_result = WorkerResult.model_validate(state["worker_result"])

        if (
            worker_result.status == "handoff"
            and worker_result.handoff is not None
            and state.get("handoff_count", 0) < max_handoffs
        ):
            return "handoff"

        return "finalize"

    return should_handoff


def build_supervisor_graph(
    worker_registry: WorkerRegistry | None = None,
    retriever=None,
    approve_tool_call=None,
    max_handoffs: int | None = None,
):
    worker_registry = worker_registry or build_default_worker_registry()
    retriever = retriever or get_retriever()
    max_handoffs = max_handoffs or get_max_handoffs()

    graph = StateGraph(SupervisorGraphState)

    graph.add_node(
        "supervisor",
        partial(supervisor_node, worker_registry=worker_registry),
    )
    graph.add_node(
        "worker",
        partial(
            worker_node,
            worker_registry=worker_registry,
            retriever=retriever,
            approve_tool_call=approve_tool_call,
        ),
    )
    graph.add_node("handoff", handoff_node)
    graph.add_node("finalize", finalize_node)

    graph.set_entry_point("supervisor")
    graph.add_edge("supervisor", "worker")
    graph.add_conditional_edges(
        "worker",
        build_should_handoff(max_handoffs),
        {
            "handoff": "handoff",
            "finalize": "finalize",
        },
    )
    graph.add_edge("handoff", "worker")
    graph.add_edge("finalize", END)

    return graph.compile()


def run_graph_supervisor(
    question: str,
    worker_registry: WorkerRegistry | None = None,
    retriever=None,
    approve_tool_call=None,
    max_handoffs: int | None = None,
) -> SupervisorResult:
    graph = build_supervisor_graph(
        worker_registry=worker_registry,
        retriever=retriever,
        approve_tool_call=approve_tool_call,
        max_handoffs=max_handoffs,
    )

    state: SupervisorGraphState = {
        "question": question,
        "handoffs": [],
        "handoff_count": 0,
    }

    final_state = graph.invoke(state)
    return SupervisorResult.model_validate(final_state["result"])


def stream_graph_supervisor(
    question: str,
    worker_registry: WorkerRegistry | None = None,
    retriever=None,
    approve_tool_call=None,
    max_handoffs: int | None = None,
) -> Iterator[str]:
    state: SupervisorGraphState = {
        "question": question,
        "handoffs": [],
        "handoff_count": 0,
    }

    try:
        graph = build_supervisor_graph(
            worker_registry=worker_registry,
            retriever=retriever,
            approve_tool_call=approve_tool_call,
            max_handoffs=max_handoffs,
        )

        for update in graph.stream(state, stream_mode="updates"):
            for node_name, node_update in update.items():
                if node_name == "supervisor" and "current_decision" in node_update:
                    decision = SupervisorDecision.model_validate(
                        node_update["current_decision"]
                    )
                    yield sse_event("decision", decision.model_dump_json())

                elif node_name == "worker" and "worker_result" in node_update:
                    worker_result = WorkerResult.model_validate(
                        node_update["worker_result"]
                    )
                    yield sse_event("worker", worker_result.model_dump_json())

                elif node_name == "handoff":
                    if node_update.get("handoffs"):
                        handoff = HandoffDecision.model_validate(
                            node_update["handoffs"][-1]
                        )
                        yield sse_event("handoff", handoff.model_dump_json())

                    if "current_decision" in node_update:
                        decision = SupervisorDecision.model_validate(
                            node_update["current_decision"]
                        )
                        yield sse_event("decision", decision.model_dump_json())

                elif node_name == "finalize" and "result" in node_update:
                    result = SupervisorResult.model_validate(node_update["result"])

                    if result.status == "completed":
                        yield sse_event("answer", result.answer)
                    else:
                        yield sse_event(
                            "error",
                            result.worker_result.error or "图执行失败",
                        )
    except Exception as exc:
        yield sse_event("error", f"LangGraph 执行失败：{exc}")

    yield sse_event("done", "")
