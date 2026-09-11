from app.models import ReactResult


# 看“必调工具”有没有被调用
def required_tool_recall(actual_tools: list[str], required_tools: list[str]) -> float:
    if not required_tools:
        return 1.0

    required = set(required_tools)
    matched = required & set(actual_tools)
    return len(matched) / len(required)


# 看“禁止工具”有没有误用
def forbidden_tool_violation(actual_tools: list[str], forbidden_tools: list[str]) -> bool:
    forbidden = set(forbidden_tools)
    return any(tool in forbidden for tool in actual_tools)


# 看答案里是否出现必须出现的关键词
def answer_keyword_coverage(answer: str, keywords: list[str]) -> float:
    if not keywords:
        return 1.0

    normalized_answer = answer.lower()
    matched = [keyword for keyword in keywords if keyword.lower() in normalized_answer]
    return len(matched) / len(keywords)


def evaluate_agent_run(result: ReactResult, case: dict) -> dict:
    actual_tools = [step.action for step in result.steps]
    required_tools = case["required_tools"]
    forbidden_tools = case.get("forbidden_tools", [])
    keywords = case.get("required_answer_keywords", [])

    tool_recall = required_tool_recall(actual_tools, required_tools)
    has_forbidden = forbidden_tool_violation(actual_tools, forbidden_tools)
    keyword_score = answer_keyword_coverage(result.answer, keywords)

    passed = tool_recall == 1.0 and not has_forbidden and keyword_score == 1.0

    return {
        "query": case["query"],
        "actual_tools": actual_tools,
        "required_tool_recall": tool_recall,
        "forbidden_tool_violation": has_forbidden,
        "answer_keyword_coverage": keyword_score,
        "passed": passed,
    }


# 汇总多个用例，得到平均指标和通过率
def evaluate_agent_runs(results: list[ReactResult], eval_set: list[dict]) -> dict:
    if not results or not eval_set:
        return {
            "avg_required_tool_recall": 0.0,
            "forbidden_violation_rate": 0.0,
            "avg_answer_keyword_coverage": 0.0,
            "pass_rate": 0.0,
            "details": [],
        }

    recalls = []
    keyword_scores = []
    passed_count = 0
    violation_count = 0
    details = []

    for result, case in zip(results, eval_set):
        detail = evaluate_agent_run(result, case)
        recalls.append(detail["required_tool_recall"])
        keyword_scores.append(detail["answer_keyword_coverage"])

        if detail["forbidden_tool_violation"]:
            violation_count += 1

        if detail["passed"]:
            passed_count += 1

        details.append(detail)

    total = len(eval_set)

    return {
        "avg_required_tool_recall": sum(recalls) / total,
        "forbidden_violation_rate": violation_count / total,
        "avg_answer_keyword_coverage": sum(keyword_scores) / total,
        "pass_rate": passed_count / total,
        "details": details,
    }