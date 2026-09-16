import argparse
import sys

from app.agent import get_retriever
from app.supervisor_graph import (
    get_graph_run,
    resume_graph_run,
    start_graph_run,
)


def print_run(run) -> None:
    print("=" * 60)
    print(f"run_id={run.run_id}")
    print(f"status={run.status}")
    print(f"next_nodes={run.next_nodes}")

    if run.error:
        print(f"error={run.error}")

    if run.result is not None:
        print(f"worker={run.result.worker_result.worker}")
        print(f"worker_status={run.result.worker_result.status}")
        print(f"answer={run.result.answer}")

    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    start_parser = subparsers.add_parser("start")
    start_parser.add_argument("question")
    start_parser.add_argument("--run-id", default=None)
    start_parser.add_argument(
        "--interrupt-before",
        action="append",
        default=None,
        help="节点名前暂停，例如 finalize",
    )

    resume_parser = subparsers.add_parser("resume")
    resume_parser.add_argument("run_id")

    state_parser = subparsers.add_parser("state")
    state_parser.add_argument("run_id")

    args = parser.parse_args()

    retriever = get_retriever()

    if args.command == "start":
        run = start_graph_run(
            args.question,
            retriever=retriever,
            run_id=args.run_id,
            interrupt_before=args.interrupt_before,
        )
        print_run(run)
        return

    if args.command == "resume":
        run = resume_graph_run(
            args.run_id,
            retriever=retriever,
        )
        print_run(run)
        return

    if args.command == "state":
        run = get_graph_run(
            args.run_id,
            retriever=retriever,
        )
        print_run(run)
        return

    parser.print_help()
    raise SystemExit(1)


if __name__ == "__main__":
    main()