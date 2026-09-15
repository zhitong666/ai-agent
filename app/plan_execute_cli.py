import argparse
import sys

from app.agent import get_retriever
from app.plan_execute import execute_plan, plan_task
from app.tools import build_default_registry


def print_plan(plan) -> None:
    print("=" * 60)
    print(f"计划目标：{plan.goal}")
    print("步骤：")

    for step in plan.steps:
        print(f"  [{step.id}] {step.goal}")
        print(f"      tool={step.tool}")
        print(f"      input={step.input}")
        print(f"      depends_on={step.depends_on}")

    print("=" * 60)


def print_result(result) -> None:
    print("\n执行轨迹：")

    for step in result.steps:
        print(f"  [{step.status}] {step.id} {step.goal}")

        if step.observation:
            print(f"      observation: {step.observation}")

    print(f"\n状态：{result.status}")

    if result.error:
        print(f"错误：{result.error}")
        return

    print(f"答案：\n{result.answer}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    parser.add_argument(
        "--max-steps",
        type=int,
        default=None,
        help="覆盖 PLAN_MAX_STEPS 环境变量",
    )
    args = parser.parse_args()

    registry = build_default_registry()

    try:
        plan = plan_task(args.question, registry)
    except Exception as exc:
        print(f"规划失败：{exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print_plan(plan)

    retriever = get_retriever()

    try:
        result = execute_plan(
            args.question,
            plan,
            registry,
            retriever,
            max_steps=args.max_steps,
        )
    except Exception as exc:
        print(f"执行失败：{exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print_result(result)

    if result.status != "completed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()