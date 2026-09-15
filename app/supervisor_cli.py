import argparse
import sys

from app.agent import get_retriever
from app.supervisor import run_supervisor
from app.workers import build_default_worker_registry


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    args = parser.parse_args()

    registry = build_default_worker_registry()
    retriever = get_retriever()

    result = run_supervisor(
        args.question,
        worker_registry=registry,
        retriever=retriever,
    )

    print("Supervisor 决策：")
    print(f"  worker={result.decision.worker}")
    print(f"  goal={result.decision.goal}")
    print(f"  reason={result.decision.reason}")
    print(f"  context={result.decision.context}")
    print()
    print(f"Worker 状态：{result.worker_result.status}")

    if result.worker_result.error:
        print(f"Worker 错误：{result.worker_result.error}")
        raise SystemExit(1)

    print()
    print("最终答案：")
    print(result.answer)


if __name__ == "__main__":
    main()