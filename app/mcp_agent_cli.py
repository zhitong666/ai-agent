import argparse

from app.mcp_agent import run_mcp_react_loop


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the agent against MCP tools",
    )
    parser.add_argument("question")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = run_mcp_react_loop(args.question)

    print("answer:", result.answer)
    print("steps:", [step.action for step in result.steps])


if __name__ == "__main__":
    main()