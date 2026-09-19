import argparse
import json

from app.agent import get_retriever
from app.shared_memory import SharedMemoryStore
from app.supervisor_graph import (
    get_graph_run,
    resume_graph_run,
    start_graph_run,
)


def build_memory_store():
    return SharedMemoryStore("data/shared_memory.sqlite")


def print_run(run) -> None:
    print("=" * 60)
    print(f"run_id={run.run_id}")
    print(f"request_id={run.request_id}")
    print(f"tenant_id={run.tenant_id}")
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
    start_parser.add_argument("--request-id", default=None)
    start_parser.add_argument("--tenant-id", default="default")
    start_parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=None,
    )

    resume_parser = subparsers.add_parser("resume")
    resume_parser.add_argument("run_id")
    resume_parser.add_argument("--tenant-id", default="default")
    resume_parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=None,
    )

    state_parser = subparsers.add_parser("state")
    state_parser.add_argument("run_id")
    state_parser.add_argument("--tenant-id", default="default")

    memory_parser = subparsers.add_parser("memory")
    memory_subparsers = memory_parser.add_subparsers(
        dest="memory_command",
        required=True,
    )

    memory_list_parser = memory_subparsers.add_parser("list")
    memory_list_parser.add_argument("run_id")
    memory_list_parser.add_argument("--tenant-id", default="default")

    memory_get_parser = memory_subparsers.add_parser("get")
    memory_get_parser.add_argument("run_id")
    memory_get_parser.add_argument("key")
    memory_get_parser.add_argument("--tenant-id", default="default")

    memory_delete_parser = memory_subparsers.add_parser("delete")
    memory_delete_parser.add_argument("run_id")
    memory_delete_parser.add_argument("key")
    memory_delete_parser.add_argument("--tenant-id", default="default")

    args = parser.parse_args()

    if args.command == "memory":
        memory = build_memory_store()
        namespace = f"tenant:{args.tenant_id}:run:{args.run_id}"

        if args.memory_command == "list":
            records = memory.list_namespace(namespace)

            for record in records:
                value = json.dumps(
                    record.value,
                    ensure_ascii=False,
                )
                print(f"{record.key}: {value}")

            return

        if args.memory_command == "get":
            record = memory.get(namespace, args.key)

            if record is None:
                print("(not found)")
                raise SystemExit(1)

            print(
                json.dumps(
                    record.value,
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return

        if args.memory_command == "delete":
            deleted = memory.delete(namespace, args.key)
            print(f"deleted={deleted}")
            return

        parser.print_help()
        raise SystemExit(1)

    retriever = get_retriever()
    memory = build_memory_store()

    if args.command == "start":
        run = start_graph_run(
            args.question,
            retriever=retriever,
            run_id=args.run_id,
            interrupt_before=args.interrupt_before,
            memory_store=memory,
            request_id=args.request_id,
            tenant_id=args.tenant_id,
            timeout_seconds=args.timeout_seconds,
        )
        print_run(run)
        return

    if args.command == "resume":
        run = resume_graph_run(
            args.run_id,
            retriever=retriever,
            memory_store=memory,
            tenant_id=args.tenant_id,
            timeout_seconds=args.timeout_seconds,
        )
        print_run(run)
        return

    if args.command == "state":
        run = get_graph_run(
            args.run_id,
            retriever=retriever,
            tenant_id=args.tenant_id,
        )
        print_run(run)
        return

    parser.print_help()
    raise SystemExit(1)


if __name__ == "__main__":
    main()