from unittest.mock import patch

from app.models import (
    SupervisorDecision,
    SupervisorResult,
    WorkerResult,
)
from app.shared_memory import SharedMemoryStore
from app.supervisor_graph import (
    _invoke_with_timeout,
    _save_run_memory,
    start_graph_run,
)


class FakeRetriever:
    def retrieve(self, query, top_k=3):
        return []


class FakeSnapshot:
    def __init__(self, values, next_nodes=(), interrupts=()):
        self.values = values
        self.next = next_nodes
        self.interrupts = interrupts


class FakeGraph:
    def __init__(self, values=None, next_nodes=(), interrupts=()):
        self.values = values or {}
        self.next_nodes = next_nodes
        self.interrupts = interrupts
        self.invoke_calls = 0

    def invoke(self, state, config=None):
        self.invoke_calls += 1
        return self.values

    def get_state(self, config):
        return FakeSnapshot(
            self.values,
            self.next_nodes,
            self.interrupts,
        )


def make_completed_values():
    decision = SupervisorDecision(
        worker="knowledge",
        goal="检索 AI Agent 学习路径",
        context="我想转 AI Agent，需要补什么？",
    )

    worker_result = WorkerResult(
        worker="knowledge",
        status="completed",
        answer="最终答案",
    )

    result = SupervisorResult(
        decision=decision,
        worker_result=worker_result,
        answer="最终答案",
        status="completed",
    )

    return {"result": result.model_dump()}


def test_invoke_with_timeout_returns_result():
    graph = FakeGraph(values={})

    result = _invoke_with_timeout(
        graph,
        {"question": "测试"},
        {},
        timeout_seconds=1,
    )

    assert result == {}


def test_start_graph_run_times_out():
    graph = FakeGraph(values=make_completed_values())
    memory = SharedMemoryStore(":memory:")

    with patch(
        "app.supervisor_graph.build_supervisor_graph",
        return_value=graph,
    ), patch(
        "app.supervisor_graph._invoke_with_timeout",
        side_effect=TimeoutError("graph run timeout after 1s"),
    ):
        run = start_graph_run(
            "我想转 AI Agent，需要补什么？",
            retriever=FakeRetriever(),
            run_id="timeout-run",
            timeout_seconds=1,
            memory_store=memory,
        )

    assert run.status == "failed"
    assert "timeout" in run.error


def test_start_graph_run_is_idempotent():
    graph = FakeGraph(values=make_completed_values())
    memory = SharedMemoryStore(":memory:")

    with patch(
        "app.supervisor_graph.build_supervisor_graph",
        return_value=graph,
    ):
        first = start_graph_run(
            "我想转 AI Agent，需要补什么？",
            retriever=FakeRetriever(),
            run_id="idempotent-run",
            request_id="request-1",
            memory_store=memory,
        )

    assert first.status == "completed"

    with patch(
        "app.supervisor_graph.get_graph_run",
        return_value=first,
    ):
        second = start_graph_run(
            "我想转 AI Agent，需要补什么？",
            retriever=FakeRetriever(),
            request_id="request-1",
            memory_store=memory,
        )

    assert second.run_id == "idempotent-run"


def test_run_namespace_isolation():
    memory = SharedMemoryStore(":memory:")

    snapshot = type(
        "Snapshot",
        (),
        {
            "run_id": "run-1",
            "tenant_id": "tenant-a",
            "status": "completed",
            "state": {},
            "result": None,
        },
    )()

    _save_run_memory(
        memory,
        "tenant-a",
        "run-1",
        snapshot,
    )

    status = memory.get("tenant:tenant-a:run:run-1", "status")

    assert status is not None
    assert status.value == "completed"