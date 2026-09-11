from app.agent_evaluate import (
    answer_keyword_coverage,
    evaluate_agent_run,
    evaluate_agent_runs,
    forbidden_tool_violation,
    required_tool_recall,
)
from app.models import ReactResult, ReactStep


def make_result(answer, tools):
    return ReactResult(
        answer=answer,
        steps=[
            ReactStep(action=tool, action_input="", observation="")
            for tool in tools
        ],
    )


def test_required_tool_recall():
    actual = ["search_knowledge", "apply_job"]
    required = ["search_knowledge", "apply_job"]

    assert required_tool_recall(actual, required) == 1.0
    assert required_tool_recall(["search_knowledge"], required) == 0.5


def test_forbidden_tool_violation():
    actual = ["search_knowledge", "apply_job"]

    assert forbidden_tool_violation(actual, ["apply_job"]) is True
    assert forbidden_tool_violation(actual, ["list_knowledge_titles"]) is False


def test_answer_keyword_coverage():
    answer = "已经为你完成 AI Agent 岗位投递。"

    assert answer_keyword_coverage(answer, ["投递"]) == 1.0
    assert answer_keyword_coverage(answer, ["投递", "RAG"]) == 0.5
    assert answer_keyword_coverage("", []) == 1.0


def test_evaluate_agent_run_passes():
    result = make_result(
        "已经为你完成 AI Agent 岗位投递。",
        ["search_knowledge", "apply_job"],
    )
    case = {
        "query": "帮我投递 AI Agent 岗位",
        "required_tools": ["apply_job"],
        "forbidden_tools": [],
        "required_answer_keywords": ["投递"],
    }

    report = evaluate_agent_run(result, case)

    assert report["required_tool_recall"] == 1.0
    assert report["forbidden_tool_violation"] is False
    assert report["answer_keyword_coverage"] == 1.0
    assert report["passed"] is True


def test_evaluate_agent_run_fails_when_forbidden_tool_used():
    result = make_result(
        "已经为你完成投递。",
        ["apply_job"],
    )
    case = {
        "query": "FastAPI 需要掌握什么",
        "required_tools": ["search_knowledge"],
        "forbidden_tools": ["apply_job"],
        "required_answer_keywords": ["FastAPI"],
    }

    report = evaluate_agent_run(result, case)

    assert report["forbidden_tool_violation"] is True
    assert report["passed"] is False


def test_evaluate_agent_runs_aggregates_metrics():
    results = [
        make_result(
            "已经完成 AI Agent 岗位投递。",
            ["search_knowledge", "apply_job"],
        ),
        make_result(
            "FastAPI 是后端框架。",
            ["search_knowledge"],
        ),
    ]

    eval_set = [
        {
            "query": "帮我分析 AI Agent 这个岗位并投递",
            "required_tools": ["apply_job"],
            "forbidden_tools": [],
            "required_answer_keywords": ["投递"],
        },
        {
            "query": "FastAPI 需要掌握什么",
            "required_tools": ["search_knowledge"],
            "forbidden_tools": ["apply_job"],
            "required_answer_keywords": ["FastAPI"],
        },
    ]

    report = evaluate_agent_runs(results, eval_set)

    assert report["avg_required_tool_recall"] == 1.0
    assert report["forbidden_violation_rate"] == 0.0
    assert report["avg_answer_keyword_coverage"] == 1.0
    assert report["pass_rate"] == 1.0