from app.models import SupervisorDecision, SupervisorResult, WorkerResult
from app.shared_memory import SharedMemoryStore
from unittest.mock import patch


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

    def invoke(self, state, config=None):
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


def test_memory_store_set_and_get():
    store = SharedMemoryStore(":memory:")

    record = store.set(
        "run:demo-1",
        "status",
        "interrupted",
    )

    loaded = store.get("run:demo-1", "status")

    assert loaded is not None
    assert loaded.key == "status"
    assert loaded.value == "interrupted"
    assert loaded.memory_id == record.memory_id


def test_memory_store_overwrites_existing_key():
    store = SharedMemoryStore(":memory:")

    store.set("run:demo-1", "answer", "old")
    store.set("run:demo-1", "answer", "new")

    loaded = store.get("run:demo-1", "answer")

    assert loaded.value == "new"


def test_memory_store_list_namespace():
    store = SharedMemoryStore(":memory:")

    store.set("run:demo-1", "status", "completed")
    store.set("run:demo-1", "answer", "最终答案")

    records = store.list_namespace("run:demo-1")

    assert len(records) == 2
    assert {record.key for record in records} == {"status", "answer"}


def test_memory_store_delete():
    store = SharedMemoryStore(":memory:")

    store.set("run:demo-1", "status", "completed")

    deleted = store.delete("run:demo-1", "status")

    assert deleted is True
    assert store.get("run:demo-1", "status") is None


def test_start_graph_run_writes_run_memory():
    values = make_completed_values()
    graph = FakeGraph(values=values)
    memory = SharedMemoryStore(":memory:")

    with patch(
        "app.supervisor_graph.build_supervisor_graph",
        return_value=graph,
    ):
        from app.supervisor_graph import start_graph_run

        start_graph_run(
            "我想转 AI Agent，需要补什么？",
            retriever=FakeRetriever(),
            run_id="demo-run-memory",
            memory_store=memory,
        )

    state = memory.get("tenant:default:run:demo-run-memory", "state")
    status = memory.get("tenant:default:run:demo-run-memory", "status")
    result = memory.get("tenant:default:run:demo-run-memory", "result")

    assert state is not None
    assert status.value == "completed"
    assert result.value["answer"] == "最终答案"