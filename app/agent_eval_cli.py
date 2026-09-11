import argparse
import json
from pathlib import Path

from app.agent_evaluate import evaluate_agent_runs
from app.evaluate import load_eval_set
from app.models import ReactResult, ReactStep
from app.react import stream_react_loop


def stream_to_result(stream) -> ReactResult:
    steps = []
    answer = ""
    error = ""

    for raw_event in stream:
        event_name = "message"
        data_lines = []

        for line in raw_event.splitlines():
            if line.startswith("event:"):
                event_name = line.removeprefix("event:").strip()
            elif line.startswith("data:"):
                data_lines.append(line.removeprefix("data:").strip())

        data = "\n".join(data_lines)

        if event_name == "step":
            payload = json.loads(data)
            steps.append(
                ReactStep(
                    action=payload["tool"],
                    action_input=payload.get("input", ""),
                    observation=payload.get("observation", ""),
                )
            )
        elif event_name == "answer":
            answer = data
        elif event_name == "error":
            error = data

    if error:
        raise RuntimeError(error)

    return ReactResult(answer=answer, steps=steps)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval-set", default="data/agent_eval_set.json")
    parser.add_argument("--max-steps", type=int, default=5)
    args = parser.parse_args()

    eval_set = load_eval_set(Path(args.eval_set))
    results = []

    for case in eval_set:
        print("运行用例：", case["query"])

        try:
            stream = stream_react_loop(
                case["query"],
                max_steps=args.max_steps,
                approve_tool_call=lambda name, arguments: True,
            )
            result = stream_to_result(stream)
        except Exception as exc:
            print("    执行失败：", exc) 
            result = ReactResult(answer=f"执行失败：{exc}", steps=[])

        results.append(result)

    report = evaluate_agent_runs(results, eval_set)

    print(f"avg_required_tool_recall: {report['avg_required_tool_recall']:.3f}")
    print(f"forbidden_violation_rate: {report['forbidden_violation_rate']:.3f}")
    print(f"avg_answer_keyword_coverage: {report['avg_answer_keyword_coverage']:.3f}")
    print(f"pass_rate: {report['pass_rate']:.3f}")

    for detail in report["details"]:
        print(detail["query"])
        print("  actual_tools:", detail["actual_tools"])
        print("  passed:", detail["passed"])


if __name__ == "__main__":
    main()