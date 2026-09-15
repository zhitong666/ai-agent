from unittest.mock import patch

from app.models import (
    HandoffDecision,
    SupervisorDecision,
    WorkerResult,
)
from app.observability import sse_to_event
from app.supervisor import (
    decide_worker,
    run_supervisor,
    stream_supervisor,
    validate_decision,
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


def test_build_default_worker_registry_contains_expected_workers():
    registry = build_default_worker_registry()

    assert set(registry.worker_names()) == {"knowledge", "jd_analysis"}


def test_decide_worker_uses_required_function():
    expected = SupervisorDecision(
        worker="knowledge",
        goal="检索 AI Agent 学习路径",
        context="我想转 AI Agent，需要补什么？",
        reason="知识库问题",
    )

    with patch(
        "app.supervisor.call_required_function",
        return_value=expected,
    ) as mock_call:
        result = decide_worker(
            "我想转 AI Agent，需要补什么？",
            build_default_worker_registry(),
        )

    assert result == expected
    assert mock_call.call_args.kwargs["tool_name"] == "save_supervisor_decision"


def test_validate_decision_rejects_unknown_worker():
    decision = SupervisorDecision(
        worker="unknown_worker",
        goal="测试",
    )

    error = validate_decision(
        decision,
        build_default_worker_registry(),
    )

    assert error == "未知 Worker: unknown_worker"


def test_run_supervisor_routes_to_knowledge_worker_without_handoff():
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

    with patch(
        "app.supervisor.decide_worker",
        return_value=decision,
    ), patch(
        "app.workers.run_knowledge_worker",
        return_value=worker_result,
    ) as mock_worker:
        registry = build_default_worker_registry()
        result = run_supervisor(
            "我想转 AI Agent，需要补什么？",
            worker_registry=registry,
            retriever=FakeRetriever(),
        )

    assert result.status == "completed"
    assert result.worker_result.answer == "最终答案"
    assert result.handoffs == []
    mock_worker.assert_called_once()


def test_run_supervisor_follows_handoff_to_next_worker():
    decision = SupervisorDecision(
        worker="knowledge",
        goal="检索 AI Agent 学习路径",
        context="字节跳动招聘 AI Agent 工程师",
    )

    first_worker_result = WorkerResult(
        worker="knowledge",
        status="handoff",
        handoff=HandoffDecision(
            target_worker="jd_analysis",
            goal="解析 JD 并生成岗位分析",
            context="字节跳动招聘 AI Agent 工程师",
            reason="输入包含 JD 特征",
        ),
    )

    second_worker_result = WorkerResult(
        worker="jd_analysis",
        status="completed",
        answer="岗位分析结果",
    )

    with patch(
        "app.supervisor.decide_worker",
        return_value=decision,
    ), patch(
        "app.workers.run_knowledge_worker",
        return_value=first_worker_result,
    ), patch(
        "app.workers.run_jd_analysis_worker",
        return_value=second_worker_result,
    ) as mock_second_worker:
        registry = build_default_worker_registry()
        result = run_supervisor(
            "字节跳动招聘 AI Agent 工程师",
            worker_registry=registry,
            retriever=FakeRetriever(),
            max_handoffs=2,
        )

    assert result.status == "completed"
    assert result.worker_result.worker == "jd_analysis"
    assert result.worker_result.answer == "岗位分析结果"
    assert len(result.handoffs) == 1
    assert result.handoffs[0].target_worker == "jd_analysis"
    mock_second_worker.assert_called_once()


def test_run_supervisor_stops_after_max_handoffs():
    decision = SupervisorDecision(
        worker="knowledge",
        goal="测试 Handoff 上限",
        context="测试",
    )

    handoff_to_jd = WorkerResult(
        worker="knowledge",
        status="handoff",
        handoff=HandoffDecision(
            target_worker="jd_analysis",
            goal="测试",
            reason="handoff 1",
        ),
    )

    handoff_to_knowledge = WorkerResult(
        worker="jd_analysis",
        status="handoff",
        handoff=HandoffDecision(
            target_worker="knowledge",
            goal="测试",
            reason="handoff 2",
        ),
    )

    with patch(
        "app.supervisor.decide_worker",
        return_value=decision,
    ), patch(
        "app.workers.run_knowledge_worker",
        return_value=handoff_to_jd,
    ), patch(
        "app.workers.run_jd_analysis_worker",
        return_value=handoff_to_knowledge,
    ):
        registry = build_default_worker_registry()
        result = run_supervisor(
            "测试",
            worker_registry=registry,
            retriever=FakeRetriever(),
            max_handoffs=1,
        )

    assert result.status == "failed"
    assert result.worker_result.error == "超过最大 Handoff 次数"
    assert len(result.handoffs) == 2


def test_stream_supervisor_emits_handoff_events():
    decision = SupervisorDecision(
        worker="knowledge",
        goal="检索 AI Agent 学习路径",
        context="字节跳动招聘 AI Agent 工程师",
    )

    first_worker_result = WorkerResult(
        worker="knowledge",
        status="handoff",
        handoff=HandoffDecision(
            target_worker="jd_analysis",
            goal="解析 JD 并生成岗位分析",
            context="字节跳动招聘 AI Agent 工程师",
            reason="输入包含 JD 特征",
        ),
    )

    second_worker_result = WorkerResult(
        worker="jd_analysis",
        status="completed",
        answer="岗位分析结果",
    )

    with patch(
        "app.supervisor.decide_worker",
        return_value=decision,
    ), patch(
        "app.workers.run_knowledge_worker",
        return_value=first_worker_result,
    ), patch(
        "app.workers.run_jd_analysis_worker",
        return_value=second_worker_result,
    ):
        registry = build_default_worker_registry()
        events = list(
            stream_supervisor(
                "字节跳动招聘 AI Agent 工程师",
                worker_registry=registry,
                retriever=FakeRetriever(),
                max_handoffs=2,
            )
        )

    event_names = [sse_to_event(raw)[0] for raw in events]
    assert event_names == [
        "decision",
        "worker",
        "handoff",
        "decision",
        "worker",
        "answer",
        "done",
    ]