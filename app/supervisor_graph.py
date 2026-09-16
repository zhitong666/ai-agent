from functools import partial
from typing import Iterator, TypedDict
import uuid
from pathlib import Path
import sqlite3
from langgraph.graph import END, StateGraph
from langgraph.checkpoint.sqlite import SqliteSaver

from app.agent import get_retriever
from app.models import (
    HandoffDecision,
    SupervisorDecision,
    SupervisorResult,
    WorkerResult,
    GraphRunStatus,
)
from app.streaming import sse_event
from app.supervisor import (
    decide_worker,
    decision_from_handoff,
    get_max_handoffs,
)
from app.workers import WorkerRegistry, build_default_worker_registry
from app.shared_memory import SharedMemoryStore


CHECKPOINT_DB_PATH = Path("data/langgraph_checkpoints.sqlite")
CHECKPOINT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def get_default_checkpointer():
    conn = sqlite3.connect(
        CHECKPOINT_DB_PATH,
        check_same_thread=False,
    )
    return SqliteSaver(conn)


DEFAULT_CHECKPOINTER = get_default_checkpointer()


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
    checkpointer=None,
    interrupt_before: list[str] | None = None,
):
    worker_registry = worker_registry or build_default_worker_registry()
    retriever = retriever or get_retriever()
    max_handoffs = max_handoffs or get_max_handoffs()
    checkpointer = checkpointer or DEFAULT_CHECKPOINTER

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

    return graph.compile(
        checkpointer=checkpointer,
        interrupt_before=interrupt_before,
    )


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


def _run_config(run_id: str) -> dict:
    return {"configurable": {"thread_id": run_id}}


def _snapshot_from_graph(
    run_id: str,
    graph,
    config: dict,
) -> GraphRunStatus:
    snapshot = graph.get_state(config)
    values = snapshot.values or {}
    next_nodes = list(snapshot.next or [])
    interrupts = list(snapshot.interrupts or [])

    result_data = values.get("result")
    result = (
        SupervisorResult.model_validate(result_data)
        if result_data is not None
        else None
    )

    if result is not None and result.status == "completed":
        status = "completed"
    elif result is not None and result.status == "failed":
        status = "failed"
    elif interrupts:
        status = "interrupted"
    elif next_nodes:
        status = "running"
    else:
        status = "failed"

    error = result.worker_result.error if result is not None else ""

    return GraphRunStatus(
        run_id=run_id,
        status=status,
        state=values,
        next_nodes=next_nodes,
        result=result,
        error=error,
    )


def start_graph_run(
    question: str,
    worker_registry: WorkerRegistry | None = None,
    retriever=None,
    approve_tool_call=None,
    max_handoffs: int | None = None,
    run_id: str | None = None,
    checkpointer=None,
    interrupt_before: list[str] | None = None, # 如果设置：interrupt_before=["finalize"] 图会在 finalize 节点前暂停。
    memory_store: SharedMemoryStore | None = None,
) -> GraphRunStatus:
    run_id = run_id or uuid.uuid4().hex
    checkpointer = checkpointer or DEFAULT_CHECKPOINTER

    graph = build_supervisor_graph(
        worker_registry=worker_registry,
        retriever=retriever,
        approve_tool_call=approve_tool_call,
        max_handoffs=max_handoffs,
        checkpointer=checkpointer,
        interrupt_before=interrupt_before,
    )

    config = _run_config(run_id)
    state: SupervisorGraphState = {
        "question": question,
        "handoffs": [],
        "handoff_count": 0,
    }

    try:
        graph.invoke(state, config=config)
    except Exception as exc:
        snapshot = _snapshot_from_graph(run_id, graph, config)
        snapshot.status = "failed"
        snapshot.error = str(exc)
        return snapshot

    snapshot = _snapshot_from_graph(run_id, graph, config)
    _save_run_memory(memory_store, run_id, snapshot)
    return snapshot


def resume_graph_run(
    run_id: str,
    worker_registry: WorkerRegistry | None = None,
    retriever=None,
    approve_tool_call=None,
    max_handoffs: int | None = None,
    checkpointer=None,
    memory_store: SharedMemoryStore | None = None,
) -> GraphRunStatus:
    checkpointer = checkpointer or DEFAULT_CHECKPOINTER

    graph = build_supervisor_graph(
        worker_registry=worker_registry,
        retriever=retriever,
        approve_tool_call=approve_tool_call,
        max_handoffs=max_handoffs,
        checkpointer=checkpointer,
        interrupt_before=None,
    )

    config = _run_config(run_id)

    try:
        graph.invoke(None, config=config) # 这里的 None 表示不是重新输入，而是从 checkpointer 保存的位置继续
    except Exception as exc:
        snapshot = _snapshot_from_graph(run_id, graph, config)
        snapshot.status = "failed"
        snapshot.error = str(exc)
        return snapshot

    snapshot = _snapshot_from_graph(run_id, graph, config)
    _save_run_memory(memory_store, run_id, snapshot)
    return snapshot


def get_graph_run(
    run_id: str,
    worker_registry: WorkerRegistry | None = None,
    retriever=None,
    approve_tool_call=None,
    checkpointer=None,
) -> GraphRunStatus:
    checkpointer = checkpointer or DEFAULT_CHECKPOINTER

    graph = build_supervisor_graph(
        worker_registry=worker_registry,
        retriever=retriever,
        approve_tool_call=approve_tool_call,
        checkpointer=checkpointer,
    )

    return _snapshot_from_graph(run_id, graph, _run_config(run_id))


def _save_run_memory(
    memory_store,
    run_id: str,
    snapshot: GraphRunStatus,
) -> None:
    if memory_store is None:
        return

    namespace = f"run:{run_id}"

    memory_store.set(namespace, "state", snapshot.state)
    memory_store.set(namespace, "status", snapshot.status)

    if snapshot.result is not None:
        memory_store.set(
            namespace,
            "result",
            snapshot.result.model_dump(),
        )