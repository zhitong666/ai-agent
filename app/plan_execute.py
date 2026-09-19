import json
import os
from collections.abc import Callable, Iterator

from app.function_calling import call_required_function
from app.guards import validate_final_answer
from app.llm import client
from app.llm_client import chat_completion_with_retry
from app.model_registry import get_model_name
from app.models import Plan, PlanExecutionResult, PlanStepState
from app.prompts import build_plan_final_answer_messages, build_plan_messages
from app.streaming import sse_event
from app.structured_output import build_tool_parameters_from_model
from app.tool_executor import execute_registered_tool

PLANNER_TOOL_NAMES = {"search_knowledge", "list_knowledge_titles"}

SAVE_PLAN_TOOL = {
    "type": "function",
    "function": {
        "name": "save_plan",
        "description": "保存任务执行计划",
        "parameters": build_tool_parameters_from_model(Plan),
    },
}


def _max_plan_steps() -> int:
    raw = os.getenv("PLAN_MAX_STEPS", "5")

    try:
        value = int(raw)
    except ValueError:
        return 5

    return max(1, min(value, 20))


def _format_tool_catalog(registry) -> str:
    lines = []

    for tool in registry.list_tools():
        if tool.name not in PLANNER_TOOL_NAMES:
            continue

        if tool.name == "search_knowledge":
            input_note = "；input 必填，放检索关键词或问题"
        elif tool.name == "list_knowledge_titles":
            input_note = "；input 留空"
        else:
            input_note = ""

        lines.append(f"- {tool.name}: {tool.description}{input_note}")

    return "\n".join(lines)


def plan_task(
    question: str,
    registry,
    *,
    model_name: str | None = None,
    max_attempts: int = 3,
) -> Plan:
    tool_catalog = _format_tool_catalog(registry)
    messages = build_plan_messages(question, tool_catalog)

    return call_required_function(
        client=client,
        messages=messages,
        tools=[SAVE_PLAN_TOOL],
        tool_name="save_plan",
        output_model=Plan,
        model_name=model_name or get_model_name(
            "planner",
            os.getenv("OPENAI_MODEL"),
        ),
        max_attempts=max_attempts,
    )


def validate_plan_structure(
    plan: Plan,
    registry,
    max_steps: int,
) -> str | None:
    if not plan.goal.strip():
        return "计划目标不能为空"

    if not plan.steps:
        return "计划至少需要 1 个步骤"

    if len(plan.steps) > max_steps:
        return f"计划步骤不能超过 {max_steps} 个"

    known_tools = set(registry.tool_names())
    seen_ids: set[str] = set()

    for step in plan.steps:
        if not step.id.strip():
            return "步骤 ID 不能为空"

        if step.id in seen_ids:
            return f"步骤 ID 重复: {step.id}"

        seen_ids.add(step.id)

        if step.tool not in known_tools:
            return f"未知工具: {step.tool}"

        if step.tool not in PLANNER_TOOL_NAMES:
            return f"工具 {step.tool} 不允许在 Day 43 Plan 中自动执行"

        if (
            step.tool == "search_knowledge"
            and not step.input.strip()
            and not step.goal.strip()
        ):
            return f"步骤 {step.id} 缺少 search_knowledge 输入"

        for dependency in step.depends_on:
            if dependency not in seen_ids:
                return f"步骤 {step.id} 依赖了尚未出现的步骤 {dependency}"

    return None


def _to_step_states(plan: Plan) -> list[PlanStepState]:
    return [
        PlanStepState(**step.model_dump())
        for step in plan.steps
    ]


def _resolve_step_input(step: PlanStepState) -> str:
    if step.tool == "search_knowledge":
        return step.input.strip() or step.goal.strip()

    return step.input


def _format_step_trace(steps: list[PlanStepState]) -> str:
    blocks = []

    for step in steps:
        blocks.append(
            f"[{step.id}] goal={step.goal}\n"
            f"tool={step.tool} input={step.input}\n"
            f"status={step.status}\n"
            f"observation={step.observation}"
        )

    return "\n\n".join(blocks)


def _generate_final_answer(
    question: str,
    steps: list[PlanStepState],
) -> str:
    trace = _format_step_trace(steps)
    messages = build_plan_final_answer_messages(question, trace)

    response = chat_completion_with_retry(
        client,
        model=get_model_name(
            "plan_final_answer",
            os.getenv("OPENAI_MODEL"),
        ),
        messages=messages,
        max_retries=3,
        timeout=10,
    )

    answer = response.choices[0].message.content or ""
    return validate_final_answer(answer)


def execute_plan(
    question: str,
    plan: Plan,
    registry,
    retriever,
    approve_tool_call: Callable[[str, dict], bool] | None = None,
    max_steps: int | None = None,
) -> PlanExecutionResult:
    if max_steps is None:
        max_steps = _max_plan_steps()

    error = validate_plan_structure(plan, registry, max_steps)

    if error:
        return PlanExecutionResult(
            plan=plan,
            steps=[],
            answer="",
            error=error,
            status="failed",
        )

    state_steps = _to_step_states(plan)
    status_by_id: dict[str, str] = {}
    failed = False

    for step in state_steps:
        missing_dependencies = [
            dependency
            for dependency in step.depends_on
            if status_by_id.get(dependency) != "completed"
        ]

        if missing_dependencies:
            step.status = "skipped"
            step.observation = (
                "依赖步骤未完成，已跳过: "
                + ", ".join(missing_dependencies)
            )
            status_by_id[step.id] = "skipped"
            failed = True
            continue

        tool = registry.get_tool(step.tool)

        if tool is None:
            step.status = "failed"
            step.observation = f"未知工具: {step.tool}"
            status_by_id[step.id] = "failed"
            failed = True
            continue

        step.status = "running"

        resolved_input = _resolve_step_input(step)
        step.input = resolved_input

        arguments: dict = {}
        if tool.input_field:
            arguments[tool.input_field] = resolved_input

        result = execute_registered_tool(
            tool,
            arguments,
            retriever,
            approve_tool_call,
        )

        step.observation = result.observation

        if not result.ok:
            step.status = "failed"
            status_by_id[step.id] = "failed"
            failed = True
            continue

        step.status = "completed"
        status_by_id[step.id] = "completed"

    if failed:
        return PlanExecutionResult(
            plan=plan,
            steps=state_steps,
            answer="",
            error="计划执行失败",
            status="failed",
        )

    answer = _generate_final_answer(question, state_steps)

    return PlanExecutionResult(
        plan=plan,
        steps=state_steps,
        answer=answer,
        status="completed",
    )


def stream_plan_execute(
    question: str,
    registry,
    retriever,
    approve_tool_call: Callable[[str, dict], bool] | None = None,
) -> Iterator[str]:
    try:
        plan = plan_task(question, registry)
    except Exception as exc:
        yield sse_event("error", f"规划失败：{exc}")
        yield sse_event("done", "")
        return

    yield sse_event("plan", plan.model_dump_json())

    result = execute_plan(
        question,
        plan,
        registry,
        retriever,
        approve_tool_call,
    )

    for step in result.steps:
        yield sse_event(
            "step",
            json.dumps(
                {
                    "id": step.id,
                    "tool": step.tool,
                    "input": step.input,
                    "status": step.status,
                    "observation": step.observation,
                },
                ensure_ascii=False,
            ),
        )

    if result.status == "completed":
        yield sse_event("answer", result.answer)
    else:
        yield sse_event("error", result.error or "计划执行失败")

    yield sse_event("done", "")