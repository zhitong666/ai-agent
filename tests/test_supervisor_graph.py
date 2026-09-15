from unittest.mock import patch

from app.models import (
    HandoffDecision,
    SupervisorDecision,
    SupervisorResult,
    WorkerResult,
)
from app.observability import sse_to_event
from app.supervisor_graph import (
    finalize_node,
    handoff_node,
    run_graph_supervisor,
    stream_graph_supervisor,
    supervisor_node,
    worker_node,
)
from app.workers import build_default_worker_registry


class FakeRetriever:
    def retrieve(self, query, top_k=3):
        return [
            {
                "doc": {
                    "chunk_id": "doc-fastapi-0",
                    "title": "FastAPI",
                    "text": "FastAPI 是 Python 后端框架。",
                },
                "score": 0.9,
            }
        ]


def test_supervisor_node_stores_decision():
    decision = SupervisorDecision(
        worker="knowledge",
        goal="检索 AI Agent 学习路径",
        context="我想转 AI Agent，需要补什么？",
    )

    state = {
        "question": "我想转 AI Agent，需要补什么？",
        "handoffs": [],
        "handoff_count": 0,
    }

    with patch(
        "app.supervisor_graph.decide_worker",
        return_value=decision,
    ):
        update = supervisor_node(
            state,
            build_default_worker_registry(),
        )

    assert update["current_decision"]["worker"] == "knowledge"


def test_worker_node_runs_selected_worker():
    decision = SupervisorDecision(
        worker="knowledge",
        goal="检索 AI Agent 学习路径",
        context="我想转 AI Agent，需要补什么？",
    )

    state = {
        "current_decision": decision.model_dump(),
        "handoffs": [],
        "handoff_count": 0,
    }

    worker_result = WorkerResult(
        worker="knowledge",
        status="completed",
        answer="最终答案",
    )

    with patch(
        "app.workers.run_knowledge_worker",
        return_value=worker_result,
    ) as mock_worker:
        update = worker_node(
            state,
            build_default_worker_registry(),
            FakeRetriever(),
            None,
        )

    assert update["worker_result"]["status"] == "completed"
    assert update["worker_result"]["answer"] == "最终答案"
    mock_worker.assert_called_once()


def test_handoff_node_builds_next_decision():
    previous_decision = SupervisorDecision(
        worker="knowledge",
        goal="检索 AI Agent 学习路径",
        context="字节跳动招聘 AI Agent 工程师",
    )

    worker_result = WorkerResult(
        worker="knowledge",
        status="handoff",
        handoff=HandoffDecision(
            target_worker="jd_analysis",
            goal="解析 JD 并生成岗位分析",
            context="字节跳动招聘 AI Agent 工程师",
            reason="输入包含 JD 特征",
        ),
    )

    state = {
        "current_decision": previous_decision.model_dump(),
        "worker_result": worker_result.model_dump(),
        "handoffs": [],
        "handoff_count": 0,
    }

    update = handoff_node(state)

    assert update["current_decision"]["worker"] == "jd_analysis"
    assert len(update["handoffs"]) == 1
    assert update["handoff_count"] == 1


def test_finalize_node_returns_completed_result():
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

    state = {
        "current_decision": decision.model_dump(),
        "worker_result": worker_result.model_dump(),
        "handoffs": [],
        "handoff_count": 0,
    }

    update = finalize_node(state)
    result = SupervisorResult.model_validate(update["result"])

    assert result.status == "completed"
    assert result.answer == "最终答案"


def test_run_graph_supervisor_uses_compiled_graph():
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

    final_result = SupervisorResult(
        decision=decision,
        worker_result=worker_result,
        answer="最终答案",
        status="completed",
    )

    class FakeGraph:
        def invoke(self, state):
            return {"result": final_result.model_dump()}

    with patch(
        "app.supervisor_graph.build_supervisor_graph",
        return_value=FakeGraph(),
    ):
        result = run_graph_supervisor(
            "我想转 AI Agent，需要补什么？",
            retriever=FakeRetriever(),
        )

    assert result.status == "completed"
    assert result.answer == "最终答案"


def test_stream_graph_supervisor_emits_expected_events():
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

    final_result = SupervisorResult(
        decision=decision,
        worker_result=worker_result,
        answer="最终答案",
        status="completed",
    )

    class FakeGraph:
        def stream(self, state, stream_mode="updates"):
            yield {"supervisor": {"current_decision": decision.model_dump()}}
            yield {"worker": {"worker_result": worker_result.model_dump()}}
            yield {"finalize": {"result": final_result.model_dump()}}

    with patch(
        "app.supervisor_graph.build_supervisor_graph",
        return_value=FakeGraph(),
    ):
        events = list(
            stream_graph_supervisor(
                "我想转 AI Agent，需要补什么？",
                retriever=FakeRetriever(),
            )
        )

    event_names = [sse_to_event(raw)[0] for raw in events]
    assert event_names == ["decision", "worker", "answer", "done"]