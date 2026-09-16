from unittest.mock import patch

from app.models import (
    SupervisorDecision,
    SupervisorResult,
    WorkerResult,
)
from app.supervisor_graph import (
    get_graph_run,
    resume_graph_run,
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
        self.invoke_calls = []

    def invoke(self, state, config=None):
        self.invoke_calls.append((state, config))
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


def test_start_graph_run_returns_interrupted_snapshot():
    graph = FakeGraph(
        values={},
        next_nodes=("finalize",),
        interrupts=("interrupt_before_finalize",),
    )

    with patch(
        "app.supervisor_graph.build_supervisor_graph",
        return_value=graph,
    ):
        run = start_graph_run(
            "我想转 AI Agent，需要补什么？",
            retriever=FakeRetriever(),
            interrupt_before=["finalize"],
        )

    assert run.status == "interrupted"
    assert run.next_nodes == ["finalize"]


def test_resume_graph_run_returns_completed_snapshot():
    values = make_completed_values()
    graph = FakeGraph(values=values)

    with patch(
        "app.supervisor_graph.build_supervisor_graph",
        return_value=graph,
    ):
        run = resume_graph_run(
            "run-123",
            retriever=FakeRetriever(),
        )

    assert run.status == "completed"
    assert run.result is not None
    assert run.result.answer == "最终答案"


def test_get_graph_run_returns_current_snapshot():
    values = make_completed_values()
    graph = FakeGraph(values=values)

    with patch(
        "app.supervisor_graph.build_supervisor_graph",
        return_value=graph,
    ):
        run = get_graph_run(
            "run-123",
            retriever=FakeRetriever(),
        )

    assert run.run_id == "run-123"
    assert run.status == "completed"
    assert run.result.answer == "最终答案"