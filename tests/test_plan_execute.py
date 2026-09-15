from unittest.mock import patch

from app.models import Plan, PlanExecutionResult, PlanStep, PlanStepState
from app.observability import sse_to_event
from app.plan_execute import execute_plan, plan_task, stream_plan_execute
from app.tool_executor import ToolExecutionResult
from app.tools import build_default_registry


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


def make_plan():
    return Plan(
        goal="分析 AI Agent 学习路径",
        steps=[
            PlanStep(
                id="step-1",
                goal="检索 FastAPI",
                tool="search_knowledge",
                input="FastAPI",
            ),
            PlanStep(
                id="step-2",
                goal="检索 AI Agent",
                tool="search_knowledge",
                input="AI Agent",
            ),
        ],
    )


def test_plan_task_returns_validated_plan():
    expected = make_plan()

    with patch(
        "app.plan_execute.call_required_function",
        return_value=expected,
    ) as mock_call:
        result = plan_task(
            "我想转 AI Agent，需要补什么",
            build_default_registry(),
        )

    assert result == expected
    assert mock_call.call_args.kwargs["tool_name"] == "save_plan"


def test_execute_plan_marks_steps_completed_and_generates_answer():
    plan = make_plan()

    with patch(
        "app.plan_execute.execute_registered_tool",
        return_value=ToolExecutionResult(True, "检索成功"),
    ), patch(
        "app.plan_execute._generate_final_answer",
        return_value="最终答案",
    ):
        result = execute_plan(
            "我想转 AI Agent，需要补什么",
            plan,
            build_default_registry(),
            FakeRetriever(),
        )

    assert result.status == "completed"
    assert [step.status for step in result.steps] == ["completed", "completed"]
    assert result.answer == "最终答案"


def test_execute_plan_marks_failed_step_failed():
    plan = make_plan()

    with patch(
        "app.plan_execute.execute_registered_tool",
        return_value=ToolExecutionResult(
            False,
            "工具 search_knowledge 执行失败: boom",
        ),
    ):
        result = execute_plan(
            "我想转 AI Agent，需要补什么",
            plan,
            build_default_registry(),
            FakeRetriever(),
        )

    assert result.status == "failed"
    assert result.steps[0].status == "failed"


def test_execute_plan_skips_step_when_dependency_failed():
    plan = Plan(
        goal="测试依赖",
        steps=[
            PlanStep(
                id="step-1",
                goal="失败步骤",
                tool="search_knowledge",
                input="x",
            ),
            PlanStep(
                id="step-2",
                goal="依赖步骤",
                tool="search_knowledge",
                input="y",
                depends_on=["step-1"],
            ),
        ],
    )

    with patch(
        "app.plan_execute.execute_registered_tool",
        return_value=ToolExecutionResult(False, "失败"),
    ) as mock_exec:
        result = execute_plan(
            "测试",
            plan,
            build_default_registry(),
            FakeRetriever(),
        )

    assert result.steps[0].status == "failed"
    assert result.steps[1].status == "skipped"
    mock_exec.assert_called_once()


def test_stream_plan_execute_emits_expected_events():
    plan = make_plan()
    result = PlanExecutionResult(
        plan=plan,
        steps=[
            PlanStepState(
                id="step-1",
                goal="检索 FastAPI",
                tool="search_knowledge",
                input="FastAPI",
                status="completed",
                observation="检索成功",
            ),
            PlanStepState(
                id="step-2",
                goal="检索 AI Agent",
                tool="search_knowledge",
                input="AI Agent",
                status="completed",
                observation="检索成功",
            ),
        ],
        answer="最终答案",
        status="completed",
    )

    with patch("app.plan_execute.plan_task", return_value=plan), patch(
        "app.plan_execute.execute_plan",
        return_value=result,
    ):
        events = list(
            stream_plan_execute(
                "我想转 AI Agent，需要补什么",
                build_default_registry(),
                FakeRetriever(),
            )
        )

    event_names = [sse_to_event(raw)[0] for raw in events]
    assert event_names == ["plan", "step", "step", "answer", "done"]


def test_execute_plan_uses_goal_when_search_input_is_empty():
    plan = Plan(
        goal="测试兜底",
        steps=[
            PlanStep(
                id="step-1",
                goal="AI Agent 岗位技能要求",
                tool="search_knowledge",
                input="",
            ),
        ],
    )

    with patch(
        "app.plan_execute.execute_registered_tool",
        return_value=ToolExecutionResult(True, "检索成功"),
    ) as mock_exec, patch(
        "app.plan_execute._generate_final_answer",
        return_value="最终答案",
    ):
        result = execute_plan(
            "测试",
            plan,
            build_default_registry(),
            FakeRetriever(),
        )

    assert result.status == "completed"
    assert result.steps[0].input == "AI Agent 岗位技能要求"
    assert mock_exec.call_args.args[1]["query"] == "AI Agent 岗位技能要求"